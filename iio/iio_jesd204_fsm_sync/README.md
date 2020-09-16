# iio_jesd204_fsm_sync

This utility resumes a number of iio devices across different IIO context from the jesd204-fsm stop-states.
It’s intended to sync multiple FPGA systems across jesd204-fsm topologies. 
There is always one primary device, the device which controls the sysref-provider and an open list of
secondary devices which are synced by the same sysref-provider connected clock source. 

Usage: iio_jesd204_fsm_sync -d <primary-device> -u <primary-uri> <secondary uris> ...

```
Example:
#iio_jesd204_fsm_sync -d adrv9009-phy -u ip10.48.65.140 ip:10.48.65.244
---------------------------------------------------------------------------
DEVICE0: adrv9009-phy uri=ip:10.48.65.140 (Primary) created
DEVICE1: adrv9009-phy uri=ip:10.48.65.244 (Secondary) created
---------------------------------------------------------------------------
DEVICE1: Is <Paused> in state <clk_sync_stage1> with status <Success (0)>
--- RESUME DEVICE1 ---
DEVICE0: Is <Paused> in state <clk_sync_stage1> with status <Success (0)>
--- RESUME DEVICE0 ---
---------------------------------------------------------------------------
DEVICE1: Is <Paused> in state <clk_sync_stage2> with status <Success (0)>
--- RESUME DEVICE1 ---
DEVICE0: Is <Paused> in state <clk_sync_stage2> with status <Success (0)>
--- RESUME DEVICE0 ---
---------------------------------------------------------------------------
DEVICE1: Is <Paused> in state <clk_sync_stage3> with status <Success (0)>
--- RESUME DEVICE1 ---
DEVICE0: Is <Paused> in state <clk_sync_stage3> with status <Success (0)>
--- RESUME DEVICE0 ---
---------------------------------------------------------------------------
DEVICE1: Is <Paused> in state <link_setup> with status <Success (0)>
--- RESUME DEVICE1 ---
DEVICE0: Is <Paused> in state <link_setup> with status <Success (0)>
--- RESUME DEVICE0 ---
---------------------------------------------------------------------------
DEVICE1: Is <Paused> in state <opt_setup_stage1> with status <Success (0)>
--- RESUME DEVICE1 ---
DEVICE0: Is <Paused> in state <opt_setup_stage1> with status <Success (0)>
--- RESUME DEVICE0 ---
---------------------------------------------------------------------------
DEVICE1: Is <Paused> in state <opt_setup_stage2> with status <Success (0)>
--- RESUME DEVICE1 ---
DEVICE0: Is <Paused> in state <opt_setup_stage2> with status <Success (0)>
--- RESUME DEVICE0 ---
---------------------------------------------------------------------------
DEVICE1: Is <Paused> in state <opt_setup_stage3> with status <Success (0)>
--- RESUME DEVICE1 ---
DEVICE0: Is <Paused> in state <opt_setup_stage3> with status <Success (0)>
--- RESUME DEVICE0 ---
---------------------------------------------------------------------------
DEVICE1: Is <Paused> in state <opt_setup_stage4> with status <Success (0)>
--- RESUME DEVICE1 ---
DEVICE0: Is <Paused> in state <opt_setup_stage4> with status <Success (0)>
--- RESUME DEVICE0 ---
---------------------------------------------------------------------------
DEVICE1: Is <Paused> in state <opt_setup_stage5> with status <Success (0)>
--- RESUME DEVICE1 ---
DEVICE0: Is <Paused> in state <opt_setup_stage5> with status <Success (0)>
--- RESUME DEVICE0 ---
---------------------------------------------------------------------------
DEVICE1: Is <Paused> in state <clocks_enable> with status <Success (0)>
--- RESUME DEVICE1 ---
DEVICE0: Is <Paused> in state <clocks_enable> with status <Success (0)>
--- RESUME DEVICE0 ---
---------------------------------------------------------------------------
DEVICE1: Is <Paused> in state <link_enable> with status <Success (0)>
--- RESUME DEVICE1 ---
DEVICE0: Is <Paused> in state <link_enable> with status <Success (0)>
--- RESUME DEVICE0 ---
---------------------------------------------------------------------------
--- DONE ---
```
