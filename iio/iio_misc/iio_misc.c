/*
 * iio_misc
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
#include <iio.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <unistd.h>

#define CHECK(expr)                                                            \
if (expr < 0) {                                                              \
	return expr;                                                               \
}

int trx_find_channels(struct iio_device *dev, int channel,
                      struct iio_channel **out0, struct iio_channel **out1)
{
    char name[16];

    snprintf(name, sizeof(name), "voltage%d_i", channel);
    *out0 = iio_device_find_channel(dev, name, 1);
    snprintf(name, sizeof(name), "voltage%d_q", channel);
    *out1 = iio_device_find_channel(dev, name, 1);

    if ((*out0 == NULL) || (*out0 == NULL))
        return -ENODEV;

    return 0;
}

int trx_phase_rotation(struct iio_device *dev, int channel, double val, double scale)
{
    struct iio_channel *out0, *out1;
    double phase, vcos, vsin;
    unsigned offset;
    int ret;

    phase = val * 2 * M_PI / 360.0;
    vcos = cos(phase) * scale;
    vsin = sin(phase) * scale;

    ret = trx_find_channels(dev, channel, &out0, &out1);
    CHECK(ret);

    if (out1 && out0) {
        ret = iio_channel_attr_write_double(out0, "calibscale", (double)vcos);
        CHECK(ret);
        ret = iio_channel_attr_write_double(out0, "calibphase", (double)(-1.0 * vsin));
        CHECK(ret);
        ret = iio_channel_attr_write_double(out1, "calibscale", (double)vcos);
        CHECK(ret);
        ret = iio_channel_attr_write_double(out1, "calibphase", (double)vsin);
        CHECK(ret);
    }

    return 0;
}

int trx_channel_xbar_set(struct iio_device *dev, int channel)
{
    struct iio_channel *out0, *out1;
    int ret, cnt, i;

    cnt = iio_device_get_channels_count(dev);

    for (i = 0; i < cnt; i++) {
        ret = trx_find_channels(dev, i, &out0, &out1);
        CHECK(ret);

        if (out1 && out0) {
            ret = iio_channel_attr_write_longlong(out0, "channel_crossbar_select", channel * 2);
            CHECK(ret);
            ret = iio_channel_attr_write_longlong(out1, "channel_crossbar_select", channel * 2 + 1);
            CHECK(ret);
        }
    }

    return 0;
}

int main(int argc, char **argv)
{
    struct iio_device *dev;
    struct iio_context *ctx;
    int opt, ret, name, xchannel = -1, channel = -1, uri = -1;
    double scale = 1.0, phase = 0.0;

    while((opt = getopt(argc, argv, "d:s:p:x:u:c:")) != -1) {

        switch(opt) {
        case 'd':
            name = optind - 1;
            break;
        case 'u':
            uri = optind - 1;
            break;
        case 's':
            scale = atof(optarg);
            break;
        case 'p':
            phase = atof(optarg);
            break;
        case 'x':
            xchannel = atoi(optarg);
            break;
        case 'c':
            channel = atoi(optarg);
            break;
        default: /* '?' */
            fprintf(stderr, "Usage: %s [-u <uri>] -d <device> -x <xbar channel> -c <channel> -p <phase> -s <scale>\n",
                    argv[0]);
            exit(EXIT_FAILURE);
        }
    }

    if (name < 0) {
        errno = EINVAL;
        perror("Missing -d <device> option");
        exit(EXIT_FAILURE);
    }

    if (uri > 0)
        ctx = iio_create_context_from_uri(argv[uri]);
    else
        ctx = iio_create_default_context();

    if (!ctx) {
        perror("Unable to create context");
        exit(EXIT_FAILURE);
    }

    dev = iio_context_find_device(ctx, argv[name]);
    if (!dev) {
        errno = ENODEV;
        perror("Unable to find device");
        goto err_destroy_context;
    }

    if (xchannel >= 0) {
        ret = trx_channel_xbar_set(dev, xchannel);
        printf("set %s X-bar all channels to voltage%d\n",
               argv[name], xchannel);
    }

    if (channel >= 0) {
        ret = trx_phase_rotation(dev, channel, phase, scale);
        if (ret == 0)
            printf("set %s voltage%d phase %f scale %f\n",
                   argv[name], channel, phase, scale);
    }

    iio_context_destroy(ctx);
    exit(EXIT_SUCCESS);

err_destroy_context:
    iio_context_destroy(ctx);
    exit(EXIT_FAILURE);
}
