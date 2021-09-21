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

#ifndef _ADIN10SPE_PHY_H_
#define _ADIN10SPE_PHY_H_

#include <net/if.h>
#include <sys/ioctl.h>
#include <linux/mdio.h>
#include <linux/mii.h>
#include <linux/sockios.h>
#include <stdbool.h>

#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))

enum adin10spe_phy_frame_control {
	NO_FRAMES = 0,
	RANDOM_PAYLOAD,
	ZEROS_PAYLOAD,
	ONES_PAYLOAD,
	ALTERNATING_ONES_PAYLOAD,
	DECREMENTING_BYTES_PAYLOAD,
};

/**
 * enum adin10spe_phy_test_modes - Test modes for MDI
 *
 * @TEST1: ADIN10SPE_PHY repeatedly transmits the data symbol sequence (+1, –1)
 * @TEST2: ADIN10SPE_PHY transmits ten “+1” symbols followed by ten “-1” symbols.
 * @TEST3: ADIN10SPE_PHY transmits as in non-test operation and in the master data mode.
 */
enum adin10spe_phy_test_modes {
	NORMAL_OP = 0,
	TEST1,
	TEST2,
	TEST3,
};

/**
 * enum adin10spe_phy_loopback_modes - Test modes for MDI
 *
 * @PMA_LOOPBACK: leave the MDI pins open-circuit, PHY receives reflection of own transmission.
 * @PCS_LOOPBACK: ADIN10SPE_PHY transmits ten “+1” symbols followed by ten “-1” symbols.
 * @MAC_LOOPBACK: ADIN10SPE_PHY transmits as in non-test operation and in the master data mode.
 */
enum adin10spe_phy_loopback_modes {
	PMA_LOOPBACK = 0,
	PCS_LOOPBACK,
	MAC_LOOPBACK,
};

/**
 * struct adin10spe_phy_frame_generator_config - Controls behaviour of Frame Generator
 *
 * @frame_control: Payload of the send frame
 * @continous_mode: true: Generate frames indefinitely, false: burst mode
 * @frame_length: As ADIN10SPE_PHY sents actual ethernet frames, this needs to be
 * 	higher than 46 (not counting dest. MAC etc.).
 * @inter_frame_gap: inter-frame gap in bytes
 * @frames_number: number of frame sent in a burst
 */
struct adin10spe_phy_frame_generator_config {
	enum adin10spe_phy_frame_control frame_control;
	bool continous_mode;
	unsigned int frame_length;
	unsigned int inter_frame_gap;
	unsigned int frames_number;
};

struct adin10spe_phy_regmap {
	/* private */
	struct ifreq ifr;
	int fd;
	int phy_id;
	char eth_name[IFNAMSIZ];
};

struct adin10spe_phy_bitfield {
	/* private */
	char *name;
	unsigned int dev_addr;
	unsigned int reg_addr;
	unsigned int bitmask;
};

enum adin10spe_phy_bf
{
	B10L_LB_PMA_LOC_EN = 0,
	B10L_TX_TEST_MODE,
	B10L_LB_PCS_EN,
	AN_EN,
	AN_FRC_MODE_EN,
	IS_AN_TX_EN,
	IS_CFG_MST,
	IS_CFG_SLV,
	IS_TX_LVL_HI,
	IS_TX_LVL_LO,
	MMD1_DEV_ID1,
	MMD1_DEV_ID2,
	CRSM_IRQ_MASK,
	CRSM_SFT_PD_CNTRL,
	CRSM_SFT_PD_RDY,
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
	RX_ERR_CNT,
	FC_FRM_CNT_H,
	FC_FRM_CNT_L,
	FC_LEN_ERR_CNT,
	FC_ALGN_ERR_CNT,
	FC_SYMB_ERR_CNT,
	FC_OSZ_CNT,
	FC_USZ_CNT,
	FC_ODD_CNT,
	FC_ODD_PRE_CNT,
	FC_FALSE_CARRIER_CNT,
	ADIN10SPE_PHY_BF_MAX,
};

/**
 * adin10spe_phy_regmap_init - Creates an adin10spe_phy_regmap
 *
 * @name: Name of the ethernet inteface (as it appears in ifconfig/ip a)
 * @phy_id: id number of the phy
 */
struct adin10spe_phy_regmap *adin10spe_phy_regmap_init(const char *name, int phy_id);

/**
 * adin10spe_phy_regmap_free - Frees an adin10spe_phy_regmap
 */
int adin10spe_phy_regmap_free(struct adin10spe_phy_regmap **regmap);

/**
 * adin10spe_phy_start_frame_generator - Starts the Frame Generator of ADIN10SPE_PHY
 *
 * @regmap: Valid adin10spe_phy_regmap
 * @cfg: see adin10spe_phy_frame_generator_config comments for details
 */
int adin10spe_phy_start_frame_generator(struct adin10spe_phy_regmap *regmap,
					 struct adin10spe_phy_frame_generator_config *cfg);
/**
 * adin10spe_phy_stop_frame_generator - Stop generating frames.
 */
int adin10spe_phy_stop_frame_generator(struct adin10spe_phy_regmap *regmap);

/**
 * adin10spe_phy_start_frame_generator - Starts a test mode
 *
 * @regmap: Valid adin10spe_phy_regmap
 * @test_mode: see adin10spe_phy_test_modes comments for details
 */
int adin10spe_phy_start_test_mode(struct adin10spe_phy_regmap *regmap,
				   enum adin10spe_phy_test_modes test_mode);

/**
 * adin10spe_phy_stop_test_mode - Stops the test mode, resumes normal operation of AIDN1100.
 */
int adin10spe_phy_stop_test_mode(struct adin10spe_phy_regmap *regmap);

/**
 * adin10spe_phy_start_loopback_mode - Starts a loopback mode
 *
 * @regmap: Valid adin10spe_phy_regmap
 * @mode: see adin10spe_phy_loopback_modes comments for details
 */
int adin10spe_phy_start_loopback_mode(struct adin10spe_phy_regmap *regmap,
				      enum adin10spe_phy_loopback_modes mode);

/**
 * adin10spe_phy_stop_test_mode - Stops the test mode, resumes normal operation of AIDN1100.
 */
int adin10spe_phy_stop_loopback_mode(struct adin10spe_phy_regmap *regmap);

/**
 * adin10spe_phy_sw_pd_mode - Enter software power-down mode
 *
 * @regmap: Valid adin10spe_phy_regmap
 * @swpd: True for software power-down mode.
 */
int adin10spe_phy_sw_pd_mode(struct adin10spe_phy_regmap *regmap, bool swpd);

int adin10spe_phy_regmap_ioctl(struct adin10spe_phy_regmap *regmap, unsigned int reg_addr,
				unsigned int write_val, unsigned int *read_val);
int adin10spe_phy_read_reg(struct adin10spe_phy_regmap *regmap, unsigned int reg_addr,
			    unsigned int *read_val);
int adin10spe_phy_write_reg(struct adin10spe_phy_regmap *regmap, unsigned int reg_addr,
			     unsigned int write_val);
int adin10spe_phy_read_reg_mmd(struct adin10spe_phy_regmap *regmap, unsigned int dev_addr,
				unsigned int reg_addr, unsigned int *read_val);
int adin10spe_phy_write_reg_mmd(struct adin10spe_phy_regmap *regmap, unsigned int dev_addr,
				 unsigned int reg_addr, unsigned int write_val);
int adin10spe_phy_update_reg_mmd(struct adin10spe_phy_regmap *regmap, unsigned int dev_addr,
				  unsigned int reg_addr, unsigned int write_val,
				  unsigned int bitmask);
int adin10spe_phy_set_bitfield(struct adin10spe_phy_regmap *regmap, enum adin10spe_phy_bf bf,
				unsigned int bitfield_val);
int adin10spe_phy_get_bitfield(struct adin10spe_phy_regmap *regmap, enum adin10spe_phy_bf bf,
				unsigned int *bitfield_val);
int adin10spe_phy_dump_bitfields(struct adin10spe_phy_regmap *regmap);

#endif /* _ADIN10SPE_PHY_H_ */
