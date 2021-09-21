/*
 * ADIN10SPE_PHY PHY cable diagnostics tool
 *
 * Copyright 2021 Analog Devices, Inc.
 *
 * Redistribution and use in source and binary forms, with or without modification,
 * are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 * this list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 * this list of conditions and the following disclaimer in the documentation and/or
 * other materials provided with the distribution.
 *
 * 3. Neither the name of the copyright holder nor the names of its contributors
 * may be used to endorse or promote products derived from this software without
 * specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
 * IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

#include <errno.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "adin10spe_phy.h"

static const char *adin10spe_phy_frame_control_modes[] = {
	"random-payload",
	"zeros-payload",
	"ones-payload",
	"alternating-ones-payload",
	"decrementing-bytes-payload",
};

static const char *adin10spe_phy_frame_output_modes[] = {
	"continous-mode",
	"burst-mode",
};

static const char *adin10spe_phy_test_modes[] = {
	"test1",
	"test2",
	"test3",
};

static const char *adin10spe_phy_lb_modes[] = {
	"pma-loopback",
	"pcs-loopback",
	"mac-loopback",
};

static int print_help()
{
	int i;

	printf("ADIN10SPE_PHY cable diagnostics control tool:\n\n");
	printf("Usage: adin10spe_phy_tool [interface name] [phy ID] [start-fg | stop-fg | start-test | stop-test | start-lb | stop-lb] ...\n");
	printf("Example: adin10spe_phy_tool eth1 0 start-loopback pcs-loopback\n");
	printf("Features:\n");
	printf("    Frame Generator:\n");
	printf("        Usage: adin10spe_phy_tool [interface name] [phy ID] [start-fg | stop-fg] [frame-control] [frame-output-mode] [frame-length] [inter-frame-gap] [frames-number]\n");
	printf("            frame-control: ");

	for (i = 0; i < ARRAY_SIZE(adin10spe_phy_frame_control_modes); i++)
		printf(" %s", adin10spe_phy_frame_control_modes[i]);
	printf("\n");

	printf("            frame-output-mode: ");

	for (i = 0; i < ARRAY_SIZE(adin10spe_phy_frame_output_modes); i++)
		printf(" %s", adin10spe_phy_frame_output_modes[i]);
	printf("\n\n");
	printf("        Example 1: adin10spe_phy_tool eth1 0 start-fg ones-payload burst-mode 100 50 10\n");
	printf("        Example 2: adin10spe_phy_tool eth1 0 stop-fg\n\n");

	printf("    Test mode:\n");
	printf("        Usage: adin10spe_phy_tool [interface name] [phy ID] [start-test | stop-test] [test-mode]\n");
	printf("            test-mode: \n");
	printf("                %s: repeatedly transmits the data symbol sequence (+1, –1)\n", adin10spe_phy_test_modes[0]);
	printf("                %s: transmits ten “+1” symbols followed by ten “-1” symbols\n", adin10spe_phy_test_modes[1]);
	printf("                %s: transmits as in non-test operation and in the master data mode\n\n", adin10spe_phy_test_modes[2]);
	printf("        Example 1: adin10spe_phy_tool eth1 0 start-test test2\n");
	printf("        Example 2: adin10spe_phy_tool eth1 0 stop-test\n\n");


	printf("    Loopback:\n");
	printf("        Usage: adin10spe_phy_tool [interface name] [phy ID] [start-lb | stop-lb] [lb-mode]\n");
	printf("            lb-mode: ");

	for (i = 0; i < ARRAY_SIZE(adin10spe_phy_lb_modes); i++)
		printf(" %s", adin10spe_phy_lb_modes[i]);
	printf("\n\n");

	printf("        Example 1: adin10spe_phy_tool eth1 0 start-lb pcs-loopback\n");
	printf("        Example 2: adin10spe_phy_tool eth1 0 stop-lb\n");

	printf("\n");
	printf("    Software power-down:\n");
	printf("        Usage: adin10spe_phy_tool [interface name] [phy ID] software-power-down [True | False]\n");
	printf("\n");

	printf("        Example : adin10spe_phy_tool eth1 0 software-power-down True\n");

	printf("\n");
	printf("    Register dump:\n");
	printf("        Usage: adin10spe_phy_tool [interface name] [phy ID] register-dump\n");
	printf("\n");

	printf("        Example : adin10spe_phy_tool eth1 0 register-dump\n");
}

static int adin10spe_phy_tool_frame_generator(struct adin10spe_phy_regmap *regmap,
					 int argc, const char** argv)
{
	struct adin10spe_phy_frame_generator_config cfg;
	int i;

	if (argc < 5)
		return -EINVAL;

	for(i = 0; i < ARRAY_SIZE(adin10spe_phy_frame_control_modes); i++)
		if (!strcmp(adin10spe_phy_frame_control_modes[i], argv[4]))
			cfg.frame_control = i + 1;

	cfg.continous_mode = !strcmp("continous-mode", argv[5]);
	cfg.frame_length = atoi(argv[6]);
	cfg.inter_frame_gap = atoi(argv[7]);

	if (!cfg.continous_mode)
		cfg.frames_number = atoi(argv[8]);

	return adin10spe_phy_start_frame_generator(regmap, &cfg);
}

static int adin10spe_phy_tool_test_mode(struct adin10spe_phy_regmap *regmap, int argc, const char** argv)
{
	enum adin10spe_phy_test_modes test_mode;
	int i;

	if (argc < 4)
		return -EINVAL;

	for(i = 0; i < ARRAY_SIZE(adin10spe_phy_test_modes); i++)
		if (!strcmp(adin10spe_phy_test_modes[i], argv[4])) {
			test_mode = i + 1;
			break;
		}

	return adin10spe_phy_start_test_mode(regmap, test_mode);
}

static int adin10spe_phy_tool_loopback(struct adin10spe_phy_regmap *regmap, int argc, const char** argv)
{
	enum adin10spe_phy_loopback_modes lb_mode;
	int i;

	if (argc < 4)
		return -EINVAL;

	for(i = 0; i < ARRAY_SIZE(adin10spe_phy_lb_modes); i++)
		if (!strcmp(adin10spe_phy_lb_modes[i], argv[4])) {
			lb_mode = i + 1;
			break;
		}

	return adin10spe_phy_start_test_mode(regmap, lb_mode);
}

static int adin10spe_phy_tool_sw_pd(struct adin10spe_phy_regmap *regmap, int argc, const char** argv)
{
	int i;

	if (argc < 4)
		return -EINVAL;

	if (!strcmp("True", argv[4]))
		return adin10spe_phy_sw_pd_mode(regmap, true);
	else
		return adin10spe_phy_sw_pd_mode(regmap, false);
}

static int adin10spe_phy_tool_reg_dump(struct adin10spe_phy_regmap *regmap, int argc,
				       const char** argv)
{
	int i;

	if (argc < 4)
		return -EINVAL;

	return adin10spe_phy_dump_bitfields(regmap);
}


int main(int argc, const char** argv)
{
	struct adin10spe_phy_regmap *regmap;
	int ret;

	if (!strcmp(argv[1], "help")) {
		print_help();
		return 0;
	}

	if (argc < 4) {
		fprintf(stderr, "See \"adin10spe_phy_tool help\" for command format.\n");
		return -EINVAL;
	}

	regmap = adin10spe_phy_regmap_init(argv[1], atoi(argv[2]));
	if (!regmap)
		return -EIO;

	if (!strcmp(argv[3], "stop-fg"))
		ret = adin10spe_phy_stop_frame_generator(regmap);
	else if (!strcmp(argv[3], "stop-test"))
		ret = adin10spe_phy_stop_test_mode(regmap);
	else if (!strcmp(argv[3], "stop-lb"))
		ret = adin10spe_phy_stop_loopback_mode(regmap);
	else if (!strcmp(argv[3], "start-fg"))
		ret = adin10spe_phy_tool_frame_generator(regmap, argc, argv);
	else if (!strcmp(argv[3], "start-test"))
		ret = adin10spe_phy_tool_test_mode(regmap, argc, argv);
	else if (!strcmp(argv[3], "start-lb"))
		ret = adin10spe_phy_tool_loopback(regmap, argc, argv);
	else if (!strcmp(argv[3], "software-power-down"))
		ret = adin10spe_phy_tool_sw_pd(regmap, argc, argv);
	else if (!strcmp(argv[3], "register-dump"))
		ret = adin10spe_phy_tool_reg_dump(regmap, argc, argv);
	else {
		fprintf(stderr, "See \"adin10spe_phy_tool help\" for command format.\n");
		adin10spe_phy_regmap_free(&regmap);
		return -EINVAL;
	}

	adin10spe_phy_regmap_free(&regmap);

	return ret;
}
