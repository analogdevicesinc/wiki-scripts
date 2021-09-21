/*
 * adin1100 PHY test modes control
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


#ifndef _ADIN1100_H_
#define _ADIN1100_H_

#include <net/if.h>
#include <sys/ioctl.h>
#include <linux/mdio.h>
#include <linux/mii.h>
#include <linux/sockios.h>
#include <stdbool.h>

#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))

enum adin1100_frame_control {
	NO_FRAMES = 0,
	RANDOM_PAYLOAD,
	ZEROS_PAYLOAD,
	ONES_PAYLOAD,
	ALTERNATING_ONES_PAYLOAD,
	DECREMENTING_BYTES_PAYLOAD,
};

/**
 * enum adin1100_test_modes - Test modes for MDI
 *
 * @TEST1: ADIN1100 repeatedly transmits the data symbol sequence (+1, –1)
 * @TEST2: ADIN1100 transmits ten “+1” symbols followed by ten “-1” symbols.
 * @TEST3: ADIN1100 transmits as in non-test operation and in the master data mode.
 */
enum adin1100_test_modes {
	NORMAL_OP = 0,
	TEST1,
	TEST2,
	TEST3,
};

/**
 * enum adin1100_loopback_modes - Test modes for MDI
 *
 * @PMA_LOOPBACK: leave the MDI pins open-circuit, PHY receives reflection of own transmission.
 * @PCS_LOOPBACK: ADIN1100 transmits ten “+1” symbols followed by ten “-1” symbols.
 * @MAC_LOOPBACK: ADIN1100 transmits as in non-test operation and in the master data mode.
 */
enum adin1100_loopback_modes {
	PMA_LOOPBACK = 0,
	PCS_LOOPBACK,
	MAC_LOOPBACK,
};

/**
 * struct adin1100_frame_generator_config - Controls behaviour of Frame Generator
 *
 * @frame_control: Payload of the send frame
 * @continous_mode: true: Generate frames indefinitely, false: burst mode
 * @frame_length: As ADIN1100 sents actual ethernet frames, this needs to be
 * 	higher than 46 (not counting dest. MAC etc.).
 * @inter_frame_gap: inter-frame gap in bytes
 * @frames_number: number of frame sent in a burst
 */
struct adin1100_frame_generator_config {
	enum adin1100_frame_control frame_control;
	bool continous_mode;
	unsigned int frame_length;
	unsigned int inter_frame_gap;
	unsigned int frames_number;
};

struct adin1100_regmap {
	/* private */
	struct ifreq ifr;
	int fd;
	int phy_id;
	char eth_name[IFNAMSIZ];
};

struct adin1100_bitfield {
	/* private */
	char *name;
	unsigned int dev_addr;
	unsigned int reg_addr;
	unsigned int bitmask;
};

enum adin1100_bf
{
	B10L_LB_PMA_LOC_EN = 0,
	B10L_TX_TEST_MODE,
	B10L_LB_PCS_EN,
	AN_EN,
	AN_FRC_MODE_EN,
	MMD1_DEV_ID1,
	MMD1_DEV_ID2,
	CRSM_IRQ_MASK,
	CRSM_SFT_PD_CNTRL,
	CRSM_DIAG_CLK_EN,
	FG_EN,
	FG_RSTRT,
	FG_CNTRL,
	FG_CONT_MODE_EN,
	FG_FRM_LEN,
	FG_IFG_LEN,
	FG_NFRM_H,
	FG_NFRM_L,
	FG_DONE,
	MAC_IF_LB_EN,
	ADIN1100_BF_MAX,
};

/**
 * adin1100_regmap_init - Creates an adin1100_regmap
 *
 * @name: Name of the ethernet inteface (as it appears in ifconfig/ip a)
 * @phy_id: id number of the phy
 */
struct adin1100_regmap *adin1100_regmap_init(const char *name, int phy_id);

/**
 * adin1100_regmap_free - Frees an adin1100_regmap
 */
int adin1100_regmap_free(struct adin1100_regmap **regmap);

/**
 * adin1100_start_frame_generator - Starts the Frame Generator of ADIN1100
 *
 * @regmap: Valid adin1100_regmap
 * @cfg: see adin1100_frame_generator_config comments for details
 */
int adin1100_start_frame_generator(struct adin1100_regmap *regmap,
				   struct adin1100_frame_generator_config *cfg);
/**
 * adin1100_stop_frame_generator - Stop generating frames.
 */
int adin1100_stop_frame_generator(struct adin1100_regmap *regmap);

/**
 * adin1100_start_frame_generator - Starts a test mode
 *
 * @regmap: Valid adin1100_regmap
 * @test_mode: see adin1100_test_modes comments for details
 */
int adin1100_start_test_mode(struct adin1100_regmap *regmap, enum adin1100_test_modes test_mode);

/**
 * adin1100_stop_test_mode - Stops the test mode, resumes normal operation of AIDN1100.
 */
int adin1100_stop_test_mode(struct adin1100_regmap *regmap);

/**
 * adin1100_start_loopback_mode - Starts a loopback mode
 *
 * @regmap: Valid adin1100_regmap
 * @mode: see adin1100_loopback_modes comments for details
 */
int adin1100_start_loopback_mode(struct adin1100_regmap *regmap, enum adin1100_loopback_modes mode);

/**
 * adin1100_stop_test_mode - Stops the test mode, resumes normal operation of AIDN1100.
 */
int adin1100_stop_loopback_mode(struct adin1100_regmap *regmap);

int adin1100_regmap_ioctl(struct adin1100_regmap *regmap, unsigned int reg_addr,
			  unsigned int write_val, unsigned int *read_val);
int adin1100_read_reg(struct adin1100_regmap *regmap, unsigned int reg_addr,
		      unsigned int *read_val);
int adin1100_write_reg(struct adin1100_regmap *regmap, unsigned int reg_addr,
		       unsigned int write_val);
int adin1100_read_reg_mmd(struct adin1100_regmap *regmap, unsigned int dev_addr,
			  unsigned int reg_addr, unsigned int *read_val);
int adin1100_write_reg_mmd(struct adin1100_regmap *regmap, unsigned int dev_addr,
			   unsigned int reg_addr, unsigned int write_val);
int adin1100_update_reg_mmd(struct adin1100_regmap *regmap, unsigned int dev_addr,
			    unsigned int reg_addr, unsigned int write_val, unsigned int bitmask);
int adin1100_set_bitfield(struct adin1100_regmap *regmap, enum adin1100_bf bf,
			  unsigned int bitfield_val);
int adin1100_get_bitfield(struct adin1100_regmap *regmap, enum adin1100_bf bf,
			  unsigned int *bitfield_val);
int adin1100_dump_bitfields(struct adin1100_regmap *regmap, struct adin1100_bitfield *bitfields);

#endif /* _ADIN1100_H_ */
