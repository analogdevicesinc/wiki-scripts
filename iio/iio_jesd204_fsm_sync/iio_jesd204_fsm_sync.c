/*
 * iio_jesd204_fsm_sync
 *
 * Copyright (C) 2020 Analog Devices, Inc.
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 * */

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <iio.h>

#define MAX_NUM_DEVICES 16

const char last[] = "opt_post_running_stage";

enum {
	DONE,
	RUNNING,
	PAUSED,
	ERR,
};

static int device_is_running(struct iio_device *dev, int i, bool verbose)
{
	char strval[80];
	long long err;
	bool paused;
	int ret;

	ret = iio_device_attr_read(dev, "jesd204_fsm_state", strval, sizeof(strval));
	if (ret < 0)
		return ret;

	ret = iio_device_attr_read_longlong(dev, "jesd204_fsm_error", &err);
	if (ret < 0)
		return ret;

	ret = iio_device_attr_read_bool(dev, "jesd204_fsm_paused", &paused);
	if (ret < 0)
		return ret;

	if (verbose)
		printf("DEVICE%d: Is <%s> in state <%s> with status <%s (%lld)>\n",
		       i, paused ? "Paused" : "Running", strval, strerror(err), err);

	if (err)
		return err;

	ret = strcmp(last, strval);

	if (ret != 0 && paused == 0)
		return RUNNING;

	if (ret != 0 && paused == 1)
		return PAUSED;

	if (ret == 0 && paused == 0)
		return DONE;

	return 0;
}

int main(int argc, char **argv)
{
	struct iio_device *dev[MAX_NUM_DEVICES];
	struct iio_context *ctx[MAX_NUM_DEVICES];
	int num, done, index, opt, ret, name = -1, uri = -1;
	char strval[80];
	long long err;
	bool paused;

	while ((opt = getopt(argc, argv, "d:u:")) != -1) {

		switch (opt) {
		case 'd':
			name = optind - 1;
			break;
		case 'u':
			uri = optind - 1;
			break;
		default: /* '?' */
			fprintf(stderr,
				"Usage: %s -d <primary-device> -u <primary-uri> <secondary uris> ...\n",
				argv[0]);
			exit(EXIT_FAILURE);
		}
	}

	if (name < 0) {
		errno = EINVAL;
		perror("Missing -d <primary-device> option");
		exit(EXIT_FAILURE);
	}

	if (uri < 0) {
		errno = EINVAL;
		perror("Missing -u <primary-uri> option");
		exit(EXIT_FAILURE);
	}

	printf("---------------------------------------------------------------------------\n");

	for (num = 0, index = optind - 1; index < argc; index++) {
		ctx[num] = iio_create_context_from_uri((num == 0) ? argv[uri] : argv[index]);
		if (!ctx[num]) {
			perror("Unable to create context");
			exit(EXIT_FAILURE);
		}
		dev[num] = iio_context_find_device(ctx[num], argv[name]);

		if (!dev[num]) {
			errno = ENODEV;
			perror("Unable to find device");
			goto err_destroy_context;
		}

		printf("DEVICE%d: %s uri=%s (%s) created\n", num, argv[name],
		       (num == 0) ? argv[uri] : argv[index],
		       (num == 0) ? "Primary" : "Secondary");

		iio_context_set_timeout(ctx[num], 20000);
		num++;

		if (num >= MAX_NUM_DEVICES)
			break;
	}

	printf("---------------------------------------------------------------------------\n");

	if (strcmp(argv[name], "adrv9009-phy") == 0)
		for (index = 0; index < num; index++)
			iio_device_debug_attr_write(dev[index], "initialize", "1");

	do {
		for (index = 0, done = 0; index < num; index++) {

			ret = device_is_running(dev[index], index, false);

			switch (ret) {
			case DONE:
				done++;
				break;
			case RUNNING:
			case PAUSED:
				break;
			default:
				goto out;
			}
		}

		if (done == num) {
			printf("--- DONE ---\n");
			goto out;
		}

		for (index = num - 1; index >= 0; index--) {
			ret = device_is_running(dev[index], index, true);
			if (ret == PAUSED) {
				printf("--- RESUME DEVICE%d ---\n", index);
				iio_device_attr_write_bool(dev[index], "jesd204_fsm_resume", 1);
			}
			if (ret < 0)
				err = ret;
		}

		printf("---------------------------------------------------------------------------\n");

	} while (err == 0);

out:
	for (index = 0; index < num; index++)
		iio_context_destroy(ctx[index]);

	exit(EXIT_SUCCESS);
err_destroy_context:
	for (index = 0; index < num; index++)
		iio_context_destroy(ctx[index]);

	exit(EXIT_FAILURE);
}
