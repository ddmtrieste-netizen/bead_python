/*
 ============================================================================
 Name        : magnetic_sensor.c
 Author      : Jurij Kotar
 Version     :
 Copyright   : Free code
 Description : Program for manetic hall effect sensor MLX90393SLQ
 Compile     : gcc -o magnetic_sensor magnetic_sensor.c -Wall -O2 -li2c
 ============================================================================
 */

#include "magnetic_sensor.h"

int read_sensor( int16_t *x, int16_t *y, int16_t *z, uint16_t *t, double *temperature )
{
	uint8_t i2c_command;
	int ret, status;
	// IOCTL packets
	struct i2c_rdwr_ioctl_data packets;
	struct i2c_msg messages[2];
	uint8_t inbuf[20];
	uint8_t outbuf[20];

	// Start Single Measurement Mode, SM, all channels
	i2c_command = 0x3f; // SM
	status = i2c_smbus_read_byte_data( i2c_fd, i2c_command );
	// Status meaning can be read from the datasheet (15.2. Status Byte).
	if ( !(status & 0x20) ) {
		printf( "ERROR: Trigger conversion, status = 0x%x\n", status );
		return -1;
	}

	// Wait for finishing the conversion, maximum time (12. Timing Specification)
	// Can be optimised
	usleep( 202300 );

	// Read Measurement, RM, all channels
	// Raw IOCTL function for complex read/write

	// Write the command
	i2c_command = 0x4f; // RM
	outbuf[0] = i2c_command;
	messages[0].addr  = i2c_address;
	messages[0].flags = 0;
	messages[0].len   = 1;
	messages[0].buf   = outbuf;

	// Read 9 bytes, status, t, x, y, z
	messages[1].addr  = i2c_address;
	messages[1].flags = I2C_M_RD;
	messages[1].len   = 9;
	messages[1].buf   = inbuf;

	packets.msgs      = messages;
	packets.nmsgs     = 2;
	// Return value, number of packets, must be 2
	ret = ioctl( i2c_fd, I2C_RDWR, &packets );

	if ( ret != 2 ) {
		printf( "ERROR: ioctl ret=%d\n", ret );
		return -1;
	}

	status = inbuf[0];
	if ( status != 0x03 ) {
		printf( "ERROR: Read Measurement, status = 0x%x\n", status );
		return -1;
	}

	// Sort the values
	*t = inbuf[1] << 8 | inbuf[2];
	*x = inbuf[3] << 8 | inbuf[4];
	*y = inbuf[5] << 8 | inbuf[6];
	*z = inbuf[7] << 8 | inbuf[8];

	*temperature = *t/45.2 + (25-46244/45.2); // Check this

	//printf( "measurement = x=%d y=%d z=%d t=%u\n", *x, *y, *z, *t );
	//printf( "HEX = x=0x%x y=0x%x z=0x%x t=0x%x\n", *x, *y, *z, *t );
	//printf( "Temperature %lf\n\n", *temperature );

	return 0;
}

int script_send_command( const char *command, char *reply, bool reply_wait )
{
	int err = -1;
	int ret, size;
	struct timespec abstime, starttime;
	double delay;
	int flags, command_size;
	int termination = 1;

	command_size = strlen( command );
	ret = write( socketfd, command, command_size );
	if ( ret == command_size ) {
		err = 0;
		if ( reply_wait ) {
			delay = 0.;
			clock_gettime( CLOCK_REALTIME, &starttime );
			size = 0;
			// Non blocking mode
			flags = fcntl( socketfd, F_GETFL );
			fcntl( socketfd, F_SETFL, flags | O_NONBLOCK );
			while ( termination && delay <  DELAY_MAX ) {
				ret = read( socketfd, &reply[size], 1000 );
				if ( ret > 0 )
						size += ret;
				// Check termination
				if ( size >= 2 )
					if ( reply[size-1] == '\r' && reply[size-2] == '\n' )
						termination = 0;
				// Calculate total delay
				clock_gettime( CLOCK_REALTIME, &abstime );
				abstime.tv_sec -= starttime.tv_sec;
				abstime.tv_nsec -= starttime.tv_nsec;
				if ( abstime.tv_nsec < 0 ) {
					abstime.tv_nsec += NSEC_PER_SEC;
					abstime.tv_sec--;
				}
				delay = abstime.tv_sec + abstime.tv_nsec / 1e9;
			}
			if ( delay >= DELAY_MAX ) {
			printf( "Waiting for readback reply expired.\n" );
			err = -1;
			}
			// Restore blocking mode
			fcntl( socketfd, F_SETFL, flags );
			// String termination
			reply[size] = 0;
		}
	}

	return err;
}

int script_get_position( double *x, double *y, double *z )
{
	int err = -1;
	char command[1000];
	char reply[1000];
	int ret;
	int enabled, moving, limit_low, limit_high;
	
	err = 0;
	
	
	// X
	if ( err == 0 ) {
		err = -1;
		sprintf( command, "<microscopeone><stepper axis=\"x\">" );
		ret = script_send_command( command, reply, true );
		if ( ret == 0 ) {
			sprintf( command, "<status></status></stepper></microscopeone>" );
			ret = script_send_command( command, reply, true );
			if ( ret == 0 ) {
				ret = sscanf( reply, "MICROSCOPEONE STEPPER status %lf %d %d %d %d", x, &enabled, &moving, &limit_low, &limit_high );
				if ( ret == 5 )
					if ( enabled == 1 && moving == 0 && limit_low == 0 && limit_high == 0 )
						err = 0;
			}
		}
	}
	// Y
	if ( err == 0 ) {
		err = -1;
		sprintf( command, "<microscopeone><stepper axis=\"y\">" );
		ret = script_send_command( command, reply, true );
		if ( ret == 0 ) {
			sprintf( command, "<status></status></stepper></microscopeone>" );
			ret = script_send_command( command, reply, true );
			if ( ret == 0 ) {
				ret = sscanf( reply, "MICROSCOPEONE STEPPER status %lf %d %d %d %d", y, &enabled, &moving, &limit_low, &limit_high );
				if ( ret == 5 )
					if ( enabled == 1 && moving == 0 && limit_low == 0 && limit_high == 0 )
						err = 0;
			}
		}
	}
	// Z
	if ( err == 0 ) {
		err = -1;
		sprintf( command, "<microscopeone><stepper axis=\"z\">" );
		ret = script_send_command( command, reply, true );
		if ( ret == 0 ) {
			sprintf( command, "<status></status></stepper></microscopeone>" );
			ret = script_send_command( command, reply, true );
			if ( ret == 0 ) {
				ret = sscanf( reply, "MICROSCOPEONE STEPPER status %lf %d %d %d %d", z, &enabled, &moving, &limit_low, &limit_high );
				if ( ret == 5 )
					if ( enabled == 1 && moving == 0 && limit_low == 0 && limit_high == 0 )
						err = 0;
			}
		}
	}
	
	return err;
}

int script_move( double x, double y, double z )
{
	char command[1000];
	char reply[1000];
	int moving_x, moving_y, moving_z;
	int tmp;
	double dtmp;
	
	//Move XYZ
	if ( script_send_command( "<microscopeone><stepper axis=\"x\">", reply, true ) != 0 ) return -1;
	sprintf( command, "<move_absolute>%lf 10000</move_absolute>", x );
	if ( script_send_command( command, reply, true ) != 0 ) return -1;
	if ( script_send_command( "</stepper>", reply, false ) != 0 ) return -1;
	
	if ( script_send_command( "<stepper axis=\"y\">", reply, true ) != 0 ) return -1;
	sprintf( command, "<move_absolute>%lf 10000</move_absolute>", y );
	if ( script_send_command( command, reply, true ) != 0 ) return -1;
	if ( script_send_command( "</stepper>", reply, false ) != 0 ) return -1;
	
	if ( script_send_command( "<stepper axis=\"z\">", reply, true ) != 0 ) return -1;
	sprintf( command, "<move_absolute>%lf 100</move_absolute>", z );
	if ( script_send_command( command, reply, true ) != 0 ) return -1;
	if ( script_send_command( "</stepper>", reply, false ) != 0 ) return -1;
	
	moving_x = 0;
	moving_y = 0;
	moving_z = 0;
	do {
		if ( script_send_command( "<stepper axis=\"x\">", reply, true ) != 0 ) return -1;
		if ( script_send_command( "<status></status></stepper>", reply, true ) != 0 ) return -1;
		sscanf( reply, "MICROSCOPEONE STEPPER status %lf %d %d %d %d", &dtmp, &tmp, &moving_x, &tmp, &tmp );
		
		if ( script_send_command( "<stepper axis=\"y\">", reply, true ) != 0 ) return -1;
		if ( script_send_command( "<status></status></stepper>", reply, true ) != 0 ) return -1;
		sscanf( reply, "MICROSCOPEONE STEPPER status %lf %d %d %d %d", &dtmp, &tmp, &moving_y, &tmp, &tmp );
		
		if ( script_send_command( "<stepper axis=\"z\">", reply, true ) != 0 ) return -1;
		if ( script_send_command( "<status></status></stepper>", reply, true ) != 0 ) return -1;
		sscanf( reply, "MICROSCOPEONE STEPPER status %lf %d %d %d %d", &dtmp, &tmp, &moving_z, &tmp, &tmp );
	} while ( abs( moving_x ) == 1 || abs( moving_y ) == 1 || abs( moving_z ) == 1 );
	
	if ( script_send_command( "</microscopeone>\n\n", reply, false ) != 0 ) return -1;
	
	return 0;
}

int main (int argc, char *argv[])
{
	int ret;
	struct addrinfo *addr, hints;
	double pos_x, pos_y, pos_z;
	double pos_x0, pos_y0, pos_z0;
	char reply[1000];
	FILE *fptr;

	if ( argc != 2 ) {
		printf("Usage: %s output_file\n", argv[0] );
		return -1;
	}

	fptr = fopen( argv[1], "w" );
	if ( fptr == NULL ) {
		printf( "Error opening the output file %s\n", argv[1] );
		return -1;
	}
	
	//
	// I2C
	//

	// I2C bus file descriptor
	i2c_fd = open( MAGNEIC_SENSOR_DEVICE, O_RDWR );
	if ( i2c_fd < 0 ) {
		printf( "Error opening I2C bus %s .\n", argv[1] );
		return -1;
	}

	// Set slave address through ioctl I2C_SLAVE
	ret = ioctl( i2c_fd, I2C_SLAVE, i2c_address );
	if( ret < 0 ) {
		printf( "Error setting I2C address.\n" );
		return -1;
	}

	//
	// Socket
	//
	// Get address
	memset( &hints, '\0', sizeof( hints ) );
	hints.ai_family = AF_INET;
	hints.ai_socktype = SOCK_STREAM;
	ret = getaddrinfo( NULL, "60000", &hints, &addr );
	if ( ret != 0) {
		error( EXIT_FAILURE, 0, "SOCKET getaddrinfo: %s", gai_strerror( ret ) );
		}

	// Open the socket
	socketfd = socket( addr->ai_family, addr->ai_socktype, addr->ai_protocol );
	//printf( "%d %d %d\n", addr->ai_family, addr->ai_socktype, addr->ai_protocol );
	if ( socketfd == -1 )
		error( EXIT_FAILURE, errno, "SOCKET socket" );

	if ( connect( socketfd, addr->ai_addr, addr->ai_addrlen) != 0 ) {
		error( EXIT_FAILURE, errno, "SOCKET connect" );
	}

	ret = script_send_command( "<temika>", reply, true );
	if ( ret == 0 )
		printf( "%s", reply );
	else
		return -1;
		
	ret = script_get_position( &pos_x0, &pos_y0, &pos_z0 ); // gets initial position
	if ( ret == 0 ) {
		printf( "Initial position x0=%lf y0=%lf z0=%lf\n", pos_x0, pos_y0, pos_z0 );
	} else {
		printf( "ERROR get_position INITIAL.\n" );
		return -1;
	}
	
	// Make X scan
	int16_t mag_x, mag_y, mag_z;
	uint16_t mag_t;
	double temperature;
	double min_x = -10000, max_x = 10000, step_x = 200;
	double min_y = 0, max_y = 0, step_y = 10;
	double min_z = 0, max_z = 0, step_z = 10;
	double cur_x, cur_y, cur_z;
	// Go to initial scan position
	pos_x = pos_x0 + min_x;
	pos_y = pos_y0 + min_y;
	pos_z = pos_z0 + min_z;
	ret = script_move( pos_x, pos_y0, pos_z0 );
	if ( ret != 0 ) {
		printf( "ERROR move.\n" );
		return -1;
	}
	fprintf( fptr, "#position_x[µm], position_y [µm], position_z [µm], magnetic_x, magnetic_y, magnetic_z, temperature_raw, temperature [℃]\n" );
	while ( pos_x <= pos_x0 + max_x ) {
		ret = script_move( pos_x, pos_y0, pos_z0 );
		if ( ret != 0 ) {
			printf( "ERROR move.\n" );
			return -1;
		}
		usleep( 100000 );
		ret = script_get_position( &cur_x, &cur_y, &cur_z );
		if ( ret != 0 ) {
			printf( "ERROR get_position.\n" );
			return -1;
		}
		if ( ret == 0 ) {
			ret = read_sensor( &mag_x, &mag_y, &mag_z, &mag_t, &temperature );
			if ( ret == 0 ) {
				printf( "position: x=%lfµm y=%lfµm z=%lfµm\n", cur_x, cur_y, cur_z );
				printf( "measurement: mag_x=%d mag_y=%d mag_z=%d t=%u temperature=%lf℃\n\n", mag_x, mag_y, mag_z, mag_t, temperature );
				fprintf( fptr, "%lf, %lf, %lf, %d, %d, %d, %u, %lf\n", cur_x, cur_y, cur_z, mag_x, mag_y, mag_z, mag_t, temperature );
			} else {
				printf( "ERROR: read_sensor.\n" );
				return -1;
			}
		}
		// Increment x
		pos_x += step_x;
	}

	return 0;
}

