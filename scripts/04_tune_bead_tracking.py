"""Tune the single-bead MOG2 tracking pipeline in one diagnostic window."""

import argparse
import time

import cv2
import numpy as np

from beadtrack import messages
from beadtrack.camera import open_camera, read_frame_or_raise
from beadtrack.detection import (
    compute_foreground_masks,
    create_background_subtractor,
    detect_largest_contour_circle,
)
from beadtrack.drawing import draw_detection, draw_track
from beadtrack.remote_view import (
    Action,
    RangeControl,
    RemoteView,
    add_display_arguments,
)

WINDOW = "Bead tracking diagnostic"
TRACKBAR_LEARNING_RATE = "Learning x1e-4 (0=auto)"
TRACKBAR_VAR_THRESHOLD = "MOG2 var threshold"
TRACKBAR_MASK_THRESHOLD = "Mask threshold"
TRACKBAR_DILATION = "Dilation"
TRACKBAR_MIN_AREA = "Minimum area"


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="Camera index.")
    parser.add_argument("--history", type=int, default=500, help="MOG2 history.")
    parser.add_argument(
        "--var-threshold",
        type=int,
        default=100,
        help="Initial MOG2 variance threshold (1-200).",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=120,
        help="Initial binary threshold (0-255); 120 includes MOG2 shadows.",
    )
    parser.add_argument(
        "--kernel", type=int, default=3, help="Odd morphology kernel size."
    )
    parser.add_argument("--dilate", type=int, default=2, help="Initial dilation (0-5).")
    parser.add_argument(
        "--min-area", type=int, default=50, help="Initial minimum area."
    )
    parser.add_argument(
        "--max-area", type=float, default=None, help="Maximum contour area."
    )
    parser.add_argument(
        "--no-shadows",
        action="store_true",
        help="Start MOG2 without shadow detection.",
    )
    parser.add_argument(
        "--panel-width",
        type=int,
        default=480,
        help="Width of each dashboard panel.",
    )
    add_display_arguments(parser)
    return parser


def validate_args(parser, args):
    if args.history <= 0:
        parser.error("--history must be positive")
    if not 1 <= args.var_threshold <= 200:
        parser.error("--var-threshold must be between 1 and 200")
    if not 0 <= args.threshold <= 255:
        parser.error("--threshold must be between 0 and 255")
    if args.kernel <= 0 or args.kernel % 2 == 0:
        parser.error("--kernel must be a positive odd number")
    if not 0 <= args.dilate <= 5:
        parser.error("--dilate must be between 0 and 5")
    if not 0 <= args.min_area <= 2000:
        parser.error("--min-area must be between 0 and 2000")
    if args.max_area is not None and args.max_area <= args.min_area:
        parser.error("--max-area must be greater than --min-area")
    if args.panel_width < 240:
        parser.error("--panel-width must be at least 240")


def create_model(history, var_threshold, detect_shadows):
    return create_background_subtractor(
        history=history,
        var_threshold=var_threshold,
        detect_shadows=detect_shadows,
    )


def _nothing(_value):
    """OpenCV trackbar callback; values are polled once per frame."""


def create_controls(args):
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.createTrackbar(TRACKBAR_LEARNING_RATE, WINDOW, 0, 100, _nothing)
    cv2.createTrackbar(
        TRACKBAR_VAR_THRESHOLD,
        WINDOW,
        args.var_threshold,
        200,
        _nothing,
    )
    cv2.createTrackbar(
        TRACKBAR_MASK_THRESHOLD,
        WINDOW,
        args.threshold,
        255,
        _nothing,
    )
    cv2.createTrackbar(TRACKBAR_DILATION, WINDOW, args.dilate, 5, _nothing)
    cv2.createTrackbar(TRACKBAR_MIN_AREA, WINDOW, args.min_area, 2000, _nothing)


def read_controls():
    return {
        "learning_position": cv2.getTrackbarPos(TRACKBAR_LEARNING_RATE, WINDOW),
        "var_threshold": max(1, cv2.getTrackbarPos(TRACKBAR_VAR_THRESHOLD, WINDOW)),
        "mask_threshold": cv2.getTrackbarPos(TRACKBAR_MASK_THRESHOLD, WINDOW),
        "dilation": cv2.getTrackbarPos(TRACKBAR_DILATION, WINDOW),
        "min_area": cv2.getTrackbarPos(TRACKBAR_MIN_AREA, WINDOW),
    }


def resolve_learning_rate(position, frozen):
    """Map the UI state to OpenCV's learningRate and a readable label."""
    if frozen:
        return 0.0, "FROZEN (learning rate 0)"
    if position == 0:
        return None, "AUTO"
    learning_rate = position / 10_000.0
    return learning_rate, f"MANUAL {learning_rate:.4f}"


def _as_bgr(image, fallback_shape):
    if image is None:
        return np.zeros(fallback_shape, dtype=np.uint8)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image.copy()


def make_panel(image, title, width):
    height = max(1, round(image.shape[0] * width / image.shape[1]))
    panel = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    cv2.rectangle(panel, (0, 0), (width, 32), (20, 20, 20), -1)
    cv2.putText(
        panel,
        title,
        (10, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return panel


def draw_telemetry(frame, fps, detection, learning_label, shadow_text):
    if detection is None:
        detection_text = "detection: NONE"
    else:
        detection_text = (
            f"x={detection.x:.1f} y={detection.y:.1f} "
            f"r={detection.radius:.1f}px area={detection.area:.1f}px2"
        )
    lines = [
        f"FPS {fps:.1f} | background {learning_label}",
        detection_text,
        shadow_text,
    ]
    for index, text in enumerate(lines):
        y = 58 + index * 24
        cv2.putText(
            frame,
            text,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )


def compose_dashboard(live, background, foreground, clean, panel_width):
    background_panel = _as_bgr(background, live.shape)
    foreground_panel = _as_bgr(foreground, live.shape)
    clean_panel = _as_bgr(clean, live.shape)
    top = np.hstack(
        (
            make_panel(live, "LIVE + DETECTION + TRAJECTORY", panel_width),
            make_panel(background_panel, "CURRENT MOG2 BACKGROUND", panel_width),
        )
    )
    bottom = np.hstack(
        (
            make_panel(
                foreground_panel,
                "RAW MOG2: 0 BACKGROUND / 127 SHADOW / 255 FOREGROUND",
                panel_width,
            ),
            make_panel(clean_panel, "FINAL MASK USED FOR DETECTION", panel_width),
        )
    )
    return np.vstack((top, bottom))


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)

    cap = None
    remote = None
    xs = []
    ys = []
    fps = 0.0
    previous_time = None
    frozen = False
    detect_shadows = not args.no_shadows
    active_var_threshold = args.var_threshold
    remote_controls = {
        "learning_position": 0,
        "var_threshold": args.var_threshold,
        "mask_threshold": args.threshold,
        "dilation": args.dilate,
        "min_area": args.min_area,
    }

    try:
        cap = open_camera(camera_index=args.camera)
        background = create_model(args.history, active_var_threshold, detect_shadows)
        if args.display == "remote":
            remote = RemoteView(
                "Bead tracking diagnostic",
                port=args.remote_port,
                controls=(
                    RangeControl(
                        "learning_position", TRACKBAR_LEARNING_RATE, 0, 100, 1, 0
                    ),
                    RangeControl(
                        "var_threshold",
                        TRACKBAR_VAR_THRESHOLD,
                        1,
                        200,
                        1,
                        args.var_threshold,
                    ),
                    RangeControl(
                        "mask_threshold",
                        TRACKBAR_MASK_THRESHOLD,
                        0,
                        255,
                        1,
                        args.threshold,
                    ),
                    RangeControl(
                        "dilation", TRACKBAR_DILATION, 0, 5, 1, args.dilate
                    ),
                    RangeControl(
                        "min_area", TRACKBAR_MIN_AREA, 0, 2000, 1, args.min_area
                    ),
                ),
                actions=(
                    Action("toggle_freeze", "Freeze / resume", (" ",)),
                    Action("reset", "Reset model", ("r",)),
                    Action("toggle_shadows", "Shadows on / off", ("s",)),
                    Action("clear_track", "Clear track", ("c",)),
                    Action("stop", "Stop", ("q", "Escape"), danger=True),
                ),
            )
            remote.start()
            messages.info(f"Remote diagnostic view: {remote.url}")
        else:
            create_controls(args)
            messages.info("Diagnostic tracking started in one window.")
            messages.info(
                "SPACE freeze/resume | r reset model | s shadows on/off | "
                "c clear track | q quit"
            )

        while True:
            if remote is not None:
                for event in remote.drain_events():
                    if event.value is not None and event.name in remote_controls:
                        remote_controls[event.name] = int(event.value)
                    elif event.name == "stop":
                        messages.result("diagnostic_tracking_stopped=true")
                        return 0
                    elif event.name == "toggle_freeze":
                        frozen = not frozen
                    elif event.name == "reset":
                        background = create_model(
                            args.history, active_var_threshold, detect_shadows
                        )
                        frozen = False
                        xs.clear()
                        ys.clear()
                    elif event.name == "toggle_shadows":
                        detect_shadows = not detect_shadows
                        background = create_model(
                            args.history, active_var_threshold, detect_shadows
                        )
                        frozen = False
                        xs.clear()
                        ys.clear()
                    elif event.name == "clear_track":
                        xs.clear()
                        ys.clear()

            frame = read_frame_or_raise(cap)

            controls = (
                dict(remote_controls) if remote is not None else read_controls()
            )
            if controls["var_threshold"] != active_var_threshold:
                active_var_threshold = controls["var_threshold"]
                background = create_model(
                    args.history, active_var_threshold, detect_shadows
                )
                frozen = False
                xs.clear()
                ys.clear()

            learning_rate, learning_label = resolve_learning_rate(
                controls["learning_position"],
                frozen,
            )
            foreground, _threshold, clean = compute_foreground_masks(
                frame,
                background,
                threshold_value=controls["mask_threshold"],
                kernel_size=args.kernel,
                dilation_iterations=controls["dilation"],
                learning_rate=learning_rate,
            )
            detection = detect_largest_contour_circle(
                clean,
                min_area=controls["min_area"],
                max_area=args.max_area,
            )
            if detection is not None:
                xs.append(detection.x)
                ys.append(detection.y)

            now = time.perf_counter()
            if previous_time is not None and now > previous_time:
                instantaneous_fps = 1.0 / (now - previous_time)
                fps = (
                    instantaneous_fps
                    if fps == 0
                    else 0.9 * fps + 0.1 * instantaneous_fps
                )
            previous_time = now

            shadow_value = int(background.getShadowValue()) if detect_shadows else None
            if shadow_value is None:
                shadow_text = "shadows OFF"
            elif controls["mask_threshold"] < shadow_value:
                shadow_text = f"shadows ON ({shadow_value}) and INCLUDED in final mask"
            else:
                shadow_text = (
                    f"shadows ON ({shadow_value}) and EXCLUDED from final mask"
                )

            live = frame.copy()
            draw_track(live, xs, ys)
            draw_detection(live, detection)
            draw_telemetry(live, fps, detection, learning_label, shadow_text)
            estimated_background = background.getBackgroundImage()
            dashboard = compose_dashboard(
                live,
                estimated_background,
                foreground,
                clean,
                args.panel_width,
            )
            if remote is not None:
                if detection is None:
                    detection_state = "none"
                else:
                    detection_state = f"{detection.x:.1f}, {detection.y:.1f}"
                remote.update_state(
                    fps=round(fps, 1),
                    detection=detection_state,
                    frozen=frozen,
                    shadows=detect_shadows,
                )
                remote.publish_frame(dashboard)
                key = 255
            else:
                cv2.imshow(WINDOW, dashboard)
                key = cv2.waitKey(1) & 0xFF

            if key in (27, ord("q")):
                messages.result("diagnostic_tracking_stopped=true")
                return 0
            if key == ord(" "):
                frozen = not frozen
            elif key == ord("r"):
                background = create_model(
                    args.history, active_var_threshold, detect_shadows
                )
                frozen = False
                xs.clear()
                ys.clear()
            elif key == ord("s"):
                detect_shadows = not detect_shadows
                background = create_model(
                    args.history, active_var_threshold, detect_shadows
                )
                frozen = False
                xs.clear()
                ys.clear()
            elif key == ord("c"):
                xs.clear()
                ys.clear()
    except KeyboardInterrupt:
        messages.warning("Diagnostic tracking interrupted.")
        return 0
    except (OSError, RuntimeError, ValueError, cv2.error) as exc:
        messages.error(exc)
        return 1
    finally:
        if cap is not None:
            cap.release()
        if remote is not None:
            remote.close()
        if args.display == "local":
            cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
