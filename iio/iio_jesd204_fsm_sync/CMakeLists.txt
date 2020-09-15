
# Copyright 2020 Analog Devices, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with GNU Radio; see the file COPYING.  If not, write to
#  the Free Software Foundation, Inc., 51 Franklin Street,
#  Boston, MA 02110-1301, USA.

cmake_minimum_required(VERSION 2.8.7)

project(iio_jesd204_fsm_sync  C)

add_executable(iio_jesd204_fsm_sync iio_jesd204_fsm_sync.c)

target_link_libraries(iio_jesd204_fsm_sync iio)
target_link_libraries(iio_jesd204_fsm_sync m)

install(TARGETS iio_jesd204_fsm_sync RUNTIME DESTINATION bin)
