/*
 * magnetic_sensor.h
 *
 *  Created on: 2 Feb 2026
 *      Author: jk400
 */

#ifndef MAGNETIC_SENSOR_H_
#define MAGNETIC_SENSOR_H_

#define DELAY_MAX 1.
#define NSEC_PER_SEC    1000000000
#define MAGNEIC_SENSOR_DEVICE "/dev/magnetic_sensor"

#include <errno.h>
#include <error.h>
#include <netdb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <time.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdbool.h>

// i2c-specific includes
#include <linux/i2c.h>
#include <linux/i2c-dev.h>
#include <i2c/smbus.h>
// support for ioctl
#include <sys/ioctl.h>

int i2c_fd;
const uint8_t i2c_address = 0x10;
int socketfd;

#endif /* MAGNETIC_SENSOR_H_ */
