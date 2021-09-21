/*
 * ADIN1100 PHY test modes control
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

#define GENMASK(h, l) (((~(unsigned int)(0)) - ((unsigned int)(1) << (l)) + 1) & (~(unsigned int)(0) >> (31 - (h))))
#define BIT(x) (1 << x)

static struct adin1100_bitfield bitfields[] = {
	{
		.name = "B10L_LB_PMA_LOC_EN",
		.dev_addr = 0x01,
		.reg_addr = 0x08F6,
		.bitmask = BIT(0),
	},
	{
		.name = "B10L_TX_TEST_MODE",
		.dev_addr = 0x01,
		.reg_addr = 0x08F8,
		.bitmask = GENMASK(15, 13),
	},
	{
		.name = "B10L_LB_PCS_EN",
		.dev_addr = 0x03,
		.reg_addr = 0x08E6,
		.bitmask = BIT(14),
	},
	{
		.name = "AN_EN",
		.dev_addr = 0x07,
		.reg_addr = 0x0200,
		.bitmask = BIT(12),
	},
	{
		.name = "AN_FRC_MODE_EN",
		.dev_addr = 0x07,
		.reg_addr = 0x8000,
		.bitmask = BIT(0),
	},
	{
		.name = "MMD1_DEV_ID1",
		.dev_addr = 0x1E,
		.reg_addr = 0x0002,
		.bitmask = GENMASK(15, 0),
	},
	{
		.name = "MMD1_DEV_ID2",
		.dev_addr = 0x1E,
		.reg_addr = 0x0003,
		.bitmask = GENMASK(15, 0),
	},
	{
		.name = "CRSM_IRQ_MASK",
		.dev_addr = 0x1E,
		.reg_addr = 0x0010,
		.bitmask = GENMASK(15, 0),
	},
	{
		.name = "CRSM_SFT_PD_CNTRL",
		.dev_addr = 0x1E,
		.reg_addr = 0x8812,
		.bitmask = BIT(0),
	},
	{
		.name = "CRSM_DIAG_CLK_EN",
		.dev_addr = 0x1E,
		.reg_addr = 0x882C,
		.bitmask = BIT(0),
	},
	{
		.name = "FG_EN",
		.dev_addr = 0x1F,
		.reg_addr = 0x8020,
		.bitmask = BIT(0),
	},
	{
		.name = "FG_RSTRT",
		.dev_addr = 0x1F,
		.reg_addr = 0x8021,
		.bitmask = BIT(3),
	},
	{
		.name = "FG_CNTRL",
		.dev_addr = 0x1F,
		.reg_addr = 0x8021,
		.bitmask = GENMASK(2, 0),
	},
	{
		.name = "FG_CONT_MODE_EN",
		.dev_addr = 0x1F,
		.reg_addr = 0x8022,
		.bitmask = BIT(0),
	},
	{
		.name = "FG_FRM_LEN",
		.dev_addr = 0x1F,
		.reg_addr = 0x8025,
		.bitmask = GENMASK(15, 0),
	},
	{
		.name = "FG_IFG_LEN",
		.dev_addr = 0x1F,
		.reg_addr = 0x8026,
		.bitmask = GENMASK(15, 0),
	},
	{
		.name = "FG_NFRM_H",
		.dev_addr = 0x1F,
		.reg_addr = 0x8027,
		.bitmask = GENMASK(15, 0),
	},
	{
		.name = "FG_NFRM_L",
		.dev_addr = 0x1F,
		.reg_addr = 0x8028,
		.bitmask = GENMASK(15, 0),
	},
	{
		.name = "FG_DONE",
		.dev_addr = 0x1F,
		.reg_addr = 0x8029,
		.bitmask = BIT(0),
	},
	{
		.name = "MAC_IF_LB_EN",
		.dev_addr = 0x1F,
		.reg_addr = 0x8055,
		.bitmask = BIT(0),
	},
};

static int mask_offset(unsigned int bitmask)
{
	int i;

	for (i = 0; i < (4 * sizeof(unsigned int)); i++)
		if ((bitmask >> i) & 0x1)
			break;

	return i;
}

struct adin1100_regmap *adin1100_regmap_init(const char *name, int phy_id)
{
	struct adin1100_regmap *regmap;

	if(!name) {
		fprintf(stderr, "Null name.\n");
		return NULL;
	}

	regmap = (struct adin1100_regmap *)calloc(1, sizeof(struct adin1100_regmap));
	if (!regmap) {
		fprintf(stderr, "Could not alloc regmap.\n");
		return NULL;
	}

	strncpy(regmap->eth_name, name, IFNAMSIZ);
	regmap->fd = socket(AF_INET, SOCK_DGRAM, 0);
	if (regmap->fd < 0) {
		fprintf(stderr, "Could not open AF_INET socket.\n");
		free(regmap);
		return NULL;
	}

	regmap->phy_id = phy_id;

	return regmap;
}

int adin1100_regmap_free(struct adin1100_regmap **regmap)
{
	if (!regmap || !regmap)
		return -EINVAL;

	close((*regmap)->fd);
	free(*regmap);
	*regmap = NULL;

	return 0;
}

int adin1100_ioctl_flags(struct adin1100_regmap *regmap, short ifru_flags)
{
	if (!regmap) {
		fprintf(stderr, "Null regamp.\n");
		return -EINVAL;
	}

	memset(&regmap->ifr, 0, sizeof(struct ifreq));
	strncpy(regmap->ifr.ifr_name, regmap->eth_name, IFNAMSIZ);
	regmap->ifr.ifr_flags |= ifru_flags;

	return ioctl(regmap->fd, SIOCSIFFLAGS, &regmap->ifr);
}

int adin1100_regmap_ioctl(struct adin1100_regmap *regmap, unsigned int reg_addr,
			  unsigned int write_val, unsigned int *read_val)
{
	struct mii_ioctl_data* mii = (struct mii_ioctl_data*)(&regmap->ifr.ifr_data);
	unsigned int ioctl_cmd;
	int ret;

	if (!regmap) {
		fprintf(stderr, "Null regamp.\n");
		return -EINVAL;
	}

	memset(&regmap->ifr, 0, sizeof(struct ifreq));
	strncpy(regmap->ifr.ifr_name, regmap->eth_name, IFNAMSIZ);

	mii->phy_id = regmap->phy_id;
	mii->reg_num = reg_addr;
	mii->val_in = write_val;
	mii->val_out = 0;

	if (read_val != NULL)
		ioctl_cmd = SIOCGMIIREG;
	else
		ioctl_cmd = SIOCSMIIREG;

	ret = ioctl(regmap->fd, ioctl_cmd, &regmap->ifr);
	if (ret < 0) {
		fprintf(stderr, "ioctl error: %d\n", ret);
		return ret;
	}

	if (read_val != NULL)
		*read_val = mii->val_out;

	return 0;
}

int adin1100_read_reg(struct adin1100_regmap *regmap, unsigned int reg_addr,
		      unsigned int *read_val)
{
	return adin1100_regmap_ioctl(regmap, reg_addr, 0, read_val);
}

int adin1100_write_reg(struct adin1100_regmap *regmap, unsigned int reg_addr,
		       unsigned int write_val)
{
	return adin1100_regmap_ioctl(regmap, reg_addr, write_val, NULL);
}

int adin1100_read_reg_mmd(struct adin1100_regmap *regmap, unsigned int dev_addr,
			  unsigned int reg_addr, unsigned int *read_val)
{
	int ret;

	/* Write the desired MMD Devad */
	ret = adin1100_write_reg(regmap, MII_MMD_CTRL, dev_addr);
	if (ret < 0)
		return ret;

	/* Write the desired MMD Devad */
	ret = adin1100_write_reg(regmap, MII_MMD_DATA, reg_addr);
	if (ret < 0)
		return ret;

	/* Select the Function : DATA with no post increment */
	ret = adin1100_write_reg(regmap, MII_MMD_CTRL, dev_addr | MII_MMD_CTRL_NOINCR);
	if (ret < 0)
		return ret;

	/* Read the content of the MMD's selected register */
	return adin1100_read_reg(regmap, MII_MMD_DATA, read_val);
}

int adin1100_write_reg_mmd(struct adin1100_regmap *regmap, unsigned int dev_addr,
			   unsigned int reg_addr, unsigned int write_val)
{
	int ret;

	/* Write the desired MMD Devad */
	ret = adin1100_write_reg(regmap, MII_MMD_CTRL, dev_addr);
	if (ret < 0)
		return ret;

	/* Write the desired MMD Devad */
	ret = adin1100_write_reg(regmap, MII_MMD_DATA, reg_addr);
	if (ret < 0)
		return ret;

	/* Select the Function : DATA with no post increment */
	ret = adin1100_write_reg(regmap, MII_MMD_CTRL, dev_addr | MII_MMD_CTRL_NOINCR);
	if (ret < 0)
		return ret;

	/* Write the data into MMD's selected register */
	return adin1100_write_reg(regmap, MII_MMD_DATA, write_val);
}

int adin1100_update_reg_mmd(struct adin1100_regmap *regmap, unsigned int dev_addr,
			    unsigned int reg_addr, unsigned int write_val, unsigned int bitmask)
{
	unsigned int read_val = 0;
	int ret;

	if (!regmap)
		return -EINVAL;

	ret = adin1100_read_reg_mmd(regmap, dev_addr, reg_addr, &read_val);
	if (ret < 0)
		return ret;

	read_val = read_val & ~bitmask;
	read_val = read_val | (bitmask & (write_val << mask_offset(bitmask)));

	return adin1100_write_reg_mmd(regmap, dev_addr, reg_addr, read_val);
}

int adin1100_set_bitfield(struct adin1100_regmap *regmap, enum adin1100_bf bf,
			  unsigned int bitfield_val)
{
	struct adin1100_bitfield *bitfield;

	if (!regmap)
		return -EINVAL;

	if (bf >= ADIN1100_BF_MAX)
		return -EINVAL;

	bitfield = &bitfields[bf];

	return adin1100_update_reg_mmd(regmap, bitfield->dev_addr, bitfield->reg_addr, bitfield_val,
				       bitfield->bitmask);
}

int adin1100_get_bitfield(struct adin1100_regmap *regmap, enum adin1100_bf bf,
			  unsigned int *bitfield_val)
{
	struct adin1100_bitfield *bitfield;
	unsigned int read_val;
	int ret;

	if (!regmap || !bitfield_val)
		return -EINVAL;

	if (bf >= ADIN1100_BF_MAX)
		return -EINVAL;

	bitfield = &bitfields[bf];

	ret = adin1100_read_reg_mmd(regmap, bitfield->dev_addr, bitfield->reg_addr, &read_val);
	if (ret < 0)
		return ret;

	*bitfield_val = (read_val & bitfield->bitmask) >> mask_offset(bitfield->bitmask);

	return 0;
}

int adin1100_start_frame_generator(struct adin1100_regmap *regmap,
				   struct adin1100_frame_generator_config *cfg)
{
	unsigned int nr_frames_high;
	unsigned int nr_frames_low;
	int ret;

	if (!regmap || !cfg)
		return -EINVAL;

	ret = adin1100_set_bitfield(regmap, CRSM_DIAG_CLK_EN, 1);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, FG_RSTRT, 0);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, FG_NFRM_H, 0);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, FG_NFRM_L, 0);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, FG_EN, 1);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, FG_FRM_LEN, cfg->frame_length);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, FG_IFG_LEN, cfg->inter_frame_gap);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, FG_CNTRL, cfg->frame_control);
	if (ret < 0)
		return ret;

	if (!cfg->continous_mode) {
		nr_frames_high = (cfg->frames_number >> 16) & GENMASK(15, 0);
		nr_frames_low = cfg->frames_number & GENMASK(15, 0);

		ret = adin1100_set_bitfield(regmap, FG_NFRM_H, nr_frames_high);
		if (ret < 0)
			return ret;

		ret = adin1100_set_bitfield(regmap, FG_NFRM_L, nr_frames_low);
		if (ret < 0)
			return ret;

		ret = adin1100_set_bitfield(regmap, FG_CONT_MODE_EN, 0);
		if (ret < 0)
			return ret;
	} else {
		ret = adin1100_set_bitfield(regmap, FG_CONT_MODE_EN, 1);
		if (ret < 0)
			return ret;
	}

	ret = adin1100_set_bitfield(regmap, FG_RSTRT, 1);
	if (ret < 0)
		return ret;

	return 0;
}

int adin1100_stop_frame_generator(struct adin1100_regmap *regmap)
{
	int ret;

	ret = adin1100_set_bitfield(regmap, FG_RSTRT, 0);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, FG_NFRM_H, 0);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, FG_NFRM_L, 0);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, FG_EN, 0);
	if (ret < 0)
		return ret;

	return adin1100_set_bitfield(regmap, CRSM_DIAG_CLK_EN, 0);
}

int adin1100_start_test_mode(struct adin1100_regmap *regmap, enum adin1100_test_modes test_mode)
{
	int ret;

	ret = adin1100_set_bitfield(regmap, CRSM_SFT_PD_CNTRL, 1);
	if (ret < 0)
		return ret;

	usleep(20000);

	ret = adin1100_set_bitfield(regmap, AN_EN, 0);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, B10L_TX_TEST_MODE, test_mode);
	if (ret < 0)
		return ret;

	return adin1100_set_bitfield(regmap, CRSM_SFT_PD_CNTRL, 0);
}

int adin1100_stop_test_mode(struct adin1100_regmap *regmap)
{
	int ret;

	ret = adin1100_set_bitfield(regmap, B10L_TX_TEST_MODE, 0);
	if (ret < 0)
		return ret;

	return adin1100_set_bitfield(regmap, AN_EN, 1);
}

int adin1100_start_loopback_mode(struct adin1100_regmap *regmap, enum adin1100_loopback_modes mode)
{
	int ret;

	switch(mode){
		case PMA_LOOPBACK:
			ret = adin1100_set_bitfield(regmap, AN_EN, 0);
			if (ret < 0)
				return ret;

			return adin1100_set_bitfield(regmap, B10L_LB_PMA_LOC_EN, 1);
		case PCS_LOOPBACK:
			return adin1100_set_bitfield(regmap, B10L_LB_PCS_EN, 1);
		case MAC_LOOPBACK:
			return adin1100_set_bitfield(regmap, MAC_IF_LB_EN, 1);
		default:
			fprintf(stderr, "ioctl error: %d\n", ret);
			return -EINVAL;
	}
}

int adin1100_stop_loopback_mode(struct adin1100_regmap *regmap)
{
	int ret;

	ret = adin1100_set_bitfield(regmap, B10L_LB_PMA_LOC_EN, 0);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, AN_EN, 1);
	if (ret < 0)
		return ret;

	ret = adin1100_set_bitfield(regmap, B10L_LB_PCS_EN, 0);
	if (ret < 0)
		return ret;

	return adin1100_set_bitfield(regmap, MAC_IF_LB_EN, 0);
}

int adin1100_dump_bitfields(struct adin1100_regmap *regmap, struct adin1100_bitfield *bitfields)
{
	unsigned int bitfield_val;
	int ret;
	int i;

	if (!regmap)
		return -EINVAL;

	printf("ADIN1100 Bitfields:\n");
	for (i = 0; i < ADIN1100_BF_MAX; i++) {
		ret = adin1100_get_bitfield(regmap, i, &bitfield_val);
		if (ret < 0)
			fprintf(stderr, "Bifield read error: %d\n", ret);
		printf("    %s: %x\n", bitfields[i].name, bitfield_val);
	}
}
