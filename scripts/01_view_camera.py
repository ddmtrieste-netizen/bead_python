import argparse

import cv2

from beadtrack import messages
from beadtrack.camera import open_camera, read_frame_or_raise
from beadtrack.remote_view import Action, RemoteView, add_display_arguments


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="View camera stream only.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index.")
    parser.add_argument("--width", type=int, default=None, help="Optional frame width.")
    parser.add_argument(
        "--height", type=int, default=None, help="Optional frame height."
    )
    parser.add_argument("--fps", type=int, default=None, help="Optional FPS request.")
    add_display_arguments(parser)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cap = None
    remote = None

    try:
        cap = open_camera(
            camera_index=args.camera,
            width=args.width,
            height=args.height,
            fps=args.fps,
        )
        if args.display == "remote":
            remote = RemoteView(
                "Beadtrack camera",
                port=args.remote_port,
                actions=(Action("stop", "Stop", ("q", "Escape"), danger=True),),
            )
            remote.start()
            messages.info(f"Remote camera view: {remote.url}")
        else:
            messages.info("Camera view started. Press q or ESC to quit.")

        while True:
            frame = read_frame_or_raise(cap)

            if remote is not None:
                remote.publish_frame(frame)
                if any(event.name == "stop" for event in remote.drain_events()):
                    return 0
            else:
                cv2.imshow("camera", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    return 0
    except KeyboardInterrupt:
        messages.warning("Camera view interrupted.")
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
