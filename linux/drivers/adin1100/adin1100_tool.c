/*
 * ADIN1100 PHY cable diagnostics tool
 *
 * Copyright (C) 2021 Analog Devices, Inc.
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
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "adin1100.h"

static const char *adin1100_frame_control_modes[] = {
	"random-payload",
	"zeros-payload",
	"ones-payload",
	"alternating-ones-payload",
	"decrementing-bytes-payload",
};

static const char *adin1100_frame_output_modes[] = {
	"continous-mode",
	"burst-mode",
};

static const char *adin1100_test_modes[] = {
	"test1",
	"test2",
	"test3",
};

static const char *adin1100_lb_modes[] = {
	"pma-loopback",
	"pcs-loopback",
	"mac-loopback",
};

static int print_help()
{
	int i;

	printf("ADIN1100 cable diagnostics control tool:\n\n");
	printf("Usage: adin1100_tool [interface name] [phy ID] [start-fg | stop-fg | start-test | stop-test | start-lb | stop-lb] ...\n");
	printf("Example: adin1100_tool eth1 0 start-loopback pcs-loopback\n");
	printf("Features:\n");
	printf("    Frame Generator:\n");
	printf("        Usage: adin1100_tool [interface name] [phy ID] [start-fg | stop-fg] [frame-control] [frame-output-mode] [frame-length] [inter-frame-gap] [frames-number]\n");
	printf("            frame-control: ");

	for (i = 0; i < ARRAY_SIZE(adin1100_frame_control_modes); i++)
		printf(" %s", adin1100_frame_control_modes[i]);
	printf("\n");

	printf("            frame-output-mode: ");

	for (i = 0; i < ARRAY_SIZE(adin1100_frame_output_modes); i++)
		printf(" %s", adin1100_frame_output_modes[i]);
	printf("\n\n");
	printf("        Example 1: adin1100_tool eth1 0 start-fg ones-payload burst-mode 100 50 10\n");
	printf("        Example 2: adin1100_tool eth1 0 stop-fg\n\n");

	printf("    Test mode:\n");
	printf("        Usage: adin1100_tool [interface name] [phy ID] [start-test | stop-test] [test-mode]\n");
	printf("            test-mode: \n");
	printf("                %s: repeatedly transmits the data symbol sequence (+1, –1)\n", adin1100_test_modes[0]);
	printf("                %s: transmits ten “+1” symbols followed by ten “-1” symbols\n", adin1100_test_modes[1]);
	printf("                %s: transmits as in non-test operation and in the master data mode\n\n", adin1100_test_modes[2]);
	printf("        Example 1: adin1100_tool eth1 0 start-test test2\n");
	printf("        Example 2: adin1100_tool eth1 0 stop-test\n\n");


	printf("    Loopback:\n");
	printf("        Usage: adin1100_tool [interface name] [phy ID] [start-lb | stop-lb] [lb-mode]\n");
	printf("            lb-mode: ");

	for (i = 0; i < ARRAY_SIZE(adin1100_lb_modes); i++)
		printf(" %s", adin1100_lb_modes[i]);
	printf("\n\n");

	printf("        Example 1: adin1100_tool eth1 0 start-lb pcs-loopback\n");
	printf("        Example 2: adin1100_tool eth1 0 stop-lb\n");
}

static int adin1100_tool_frame_generator(struct adin1100_regmap *regmap,
					 int argc, const char** argv)
{
	struct adin1100_frame_generator_config cfg;
	int i;

	if (argc < 7)
		return -EINVAL;

	for(i = 0; i < ARRAY_SIZE(adin1100_frame_control_modes); i++)
		if (strcmp(adin1100_frame_control_modes[i], argv[4]))
			cfg.frame_control = i + 1;

	cfg.continous_mode = !strcmp("continous-mode", argv[5]);
	cfg.frame_length = atoi(argv[6]);
	cfg.inter_frame_gap = atoi(argv[7]);

	if (!cfg.continous_mode)
		cfg.frames_number = atoi(argv[8]);

	return adin1100_start_frame_generator(regmap, &cfg);
}

static int adin1100_tool_test_mode(struct adin1100_regmap *regmap, int argc, const char** argv)
{
	enum adin1100_test_modes test_mode;
	int i;

	if (argc < 5)
		return -EINVAL;

	for(i = 0; i < ARRAY_SIZE(adin1100_test_modes); i++)
		if (strcmp(adin1100_test_modes[i], argv[4])) {
			test_mode = i + 1;
			break;
		}

	return adin1100_start_test_mode(regmap, test_mode);
}

static int adin1100_tool_loopback(struct adin1100_regmap *regmap, int argc, const char** argv)
{
	enum adin1100_loopback_modes lb_mode;
	int i;

	if (argc < 5)
		return -EINVAL;

	for(i = 0; i < ARRAY_SIZE(adin1100_lb_modes); i++)
		if (strcmp(adin1100_lb_modes[i], argv[4])) {
			lb_mode = i + 1;
			break;
		}

	return adin1100_start_test_mode(regmap, lb_mode);
}

int main(int argc, const char** argv)
{
	struct adin1100_regmap *regmap;
	int ret;

	if (!strcmp(argv[1], "help")) {
		print_help();
		return 0;
	}

	if (argc < 4) {
		fprintf(stderr, "See \"adin1100_tool help\" for command format.\n");
		return -EINVAL;
	}

	regmap = adin1100_regmap_init(argv[1], atoi(argv[2]));
	if (!regmap)
		return -EIO;

	if (!strcmp(argv[3], "stop-fg"))
		ret = adin1100_stop_frame_generator(regmap);
	else if (!strcmp(argv[3], "stop-test"))
		ret = adin1100_stop_test_mode(regmap);
	else if (!strcmp(argv[3], "stop-lb"))
		ret = adin1100_stop_loopback_mode(regmap);
	else if (!strcmp(argv[3], "start-fg"))
		ret = adin1100_tool_frame_generator(regmap, argc, argv);
	else if (!strcmp(argv[3], "start-test"))
		ret = adin1100_tool_test_mode(regmap, argc, argv);
	else if (!strcmp(argv[3], "start-lb"))
		ret = adin1100_tool_loopback(regmap, argc, argv);
	else {
		fprintf(stderr, "See \"adin1100_tool help\" for command format.\n");
		adin1100_regmap_free(&regmap);
		return -EINVAL;
	}

	adin1100_regmap_free(&regmap);

	return ret;
}
