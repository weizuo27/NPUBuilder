import os.path
import struct
import sys
import pprint
import argparse
import math
VALIDATE = 0


class Phase():
    def __init__(self):
        self.Data = None
        self.Total_latency = None
        self.W_start_row = None
        self.W_end_row = None
        self.R_start_row = None
        self.R_end_row = None

    def set_latency_info(self, data0, data1, non_racing_latency):
        self.Total_latency = non_racing_latency
        self.Data = (data0, data1)

    def set_write_row_info(self, start_row, end_row):
        self.W_start_row = start_row
        self.W_end_row = end_row

    def set_read_row_info(self, start_row, end_row):
        self.R_start_row = start_row
        self.R_end_row = end_row


def _align_size(x, y):
    return -int(-x//y)*y


def _ceil_div(x, y):
    """
    Cell division

    """
    return -int(-x//y)


# FXD

class ConvIP():
    ker_factor_list = [0, 8, 16, 24, 32]
    pix_factor_list = [0, 8, 16, 24, 32, 48]

    """
    get_[xxxx] function shall change object attribute based on calcalutaions
    get_[XXXX]_latency function shall change both object write latency into latency info
    _[xxxxx] are helpler function which change nothing
    """

    def __init__(self, cls=0, ker_factor=0, pix_factor=0, input_buffer_depth=0, output_buffer_depth=0, weight_buffer_depth=0):
        """
        initialization of the class
        input: 
            ker_factor: hardware factor XI_KER_PROC
            pix_factor: hardware factor XI_PIX_PROC
            input_buffer_depth: the depth of input buffer
            output_buffer_depth: the depth of output buffer
            weight_buffer_depth: the depth of input buffer
        """
        assert(ker_factor in cls.ker_factor_list), "Invalid Ker factor of {}\n".format(
            ker_factor)
        self._ker_factor = ker_factor

        assert(pix_factor in cls.pix_factor_list), "Invalid Pix factor of {}\n".format(
            pix_factor)
        self._pix_factor = pix_factor

        self._input_buffer_depth = input_buffer_depth
        self._output_buffer_depth = output_buffer_depth
        self._weight_buffer_depth = weight_buffer_depth

        # latency dictionary
        self._latency_dict = {}
        # constant setting
        self._feeding_buffer_size = 1024
        self._overall_overhead = 2500

        # hardware time constant
        self.CLK_PERIOD = 4.0
        self.COMPUTEKER_OVERHEAD = 20
        self.OSTGBUFFSEQ_OVERHEAD = 10
        self.LOADFEEDINGBUFFER_OVERHEAD = 10

        # axi constant
        self.AXI_ACK_CYCLE = 3.5
        self.AXI_RESPONSE_CYCLE = 24
        self.AXI_ACK_CYCLE_WRITE = 7
        self.AXI_RESPONSE_CYCLE_WRITE = 20

        # FIXME: debugging purpose variable, need to be deleted
        self._first_read_flag = True

    def set_from_IPInfo(self, IPInfo):
        self._ker_factor = IPInfo.XI_KER_PROC
        self._pix_factor = IPInfo.XI_PIX_PROC
        self._input_buffer_depth = IPInfo.XI_INDEPTH
        self._output_buffer_depth = IPInfo.XI_OUTDEPTH
        self._weight_buffer_depth = IPInfo.XI_WEIGHTBUFF_DEPTH

    def load_layer(self, conv_layer_info):
        self.Layer = conv_layer_info
        self._latency_dict['RowStep'] = self.Layer._row_step
        self.Layer._channels_in = _align_size(self.Layer._channels_in, 4)

    def _pingpong_latency_helpler(self, ping_latency, pong_latency, number):
        return ping_latency + pong_latency + (number-1)*max(ping_latency, pong_latency)

    def _mem_burst_read_latency(self, burst_number, burst_length, burst_overhead):
        """
        computes the function latency and bandwidth latency of a sequence of burstReads
        return: totalCycle: the total cycle number such sequence of burst read takes
                dataCycle: the total cycle number for data transfer such sequence of burst read takes ( it will be in conflict with other read)
        input burstNumber: the number of burst read in the burst sequence
        input burstLength: the length of each burst read
        input burstOverhead: the cycle number between the time last burst read data is receive till the start of issurance of next burst read
        """
        if(burst_length == 0):
            return 0, 0
        burst_breaks = _ceil_div(burst_length, 16)

        data_cycle = (burst_length+burst_breaks *
                      self.AXI_ACK_CYCLE)*burst_number

        total_cycle = (burst_overhead + self.AXI_RESPONSE_CYCLE) * \
            burst_number + data_cycle

        return total_cycle, data_cycle

    def _mem_burst_write_latency(self, burst_number, burst_length, burst_overhead):
        """
        computes the function latency and bandwidth latency of a sequence of burstReads
        return: totalCycle: the total cycle number such sequence of burst read takes
                dataCycle: the total cycle number for data transfer such sequence of burst read takes ( it will be in conflict with other read)
        input burstNumber: the number of burst read in the burst sequence
        input burstLength: the length of each burst read
        input burstOverhead: the cycle number between the time last burst read data is receive till the start of issurance of next burst read
        """
        if(burst_length == 0):
            return 0, 0
        burst_breaks = _ceil_div(burst_length, 16)

        data_cycle = (burst_length+burst_breaks *
                      self.AXI_ACK_CYCLE_WRITE)*burst_number

        total_cycle = (burst_overhead + self.AXI_RESPONSE_CYCLE_WRITE) * \
            burst_number + data_cycle

        return total_cycle, data_cycle

    def clean_latency_info(self):
        """
        clean out all the latency info and layer info
        """

        # clean mounted layer
        self.Layer = None

        # clean latency information dictionary
        self._latency_dict = {}

        # clean attributes from get_channels_in_tile_size
        self._channel_in_tile_number = None
        self._channel_in_tile_size = None
        self._window_size_square = None

        # attributes from get_channels_out_tile_size
        self._channels_out_tile_size = None
        self._channels_out_tile_size_last = None
        self._channels_out_tile_number = None

        # attributes from get_channels_out_tile_size
        self._conversion_iter_number = None
        self._load_input_tile_latency = None

    def get_channels_in_tile_size(self):
        """
        Compute the Input depth(channel) tile size based on the estimated latency of LoadFeedingbuffer

        Generated dictionary items:
            self._compute_iter_length 
            self._window_size_square 
            self._channel_in_tile_size 
            self._channel_in_tile_number 
        """
        channels_in_align4 = _align_size(self.Layer._channels_in, 4)
        if channels_in_align4 < 4:
            split = 1
        else:
            split = self.Layer._group_number

        window_size_sqare = self.Layer._window_size*self.Layer._window_size
        buffer_capacity = (self._feeding_buffer_size/2-1) // \
            (window_size_sqare)

        channel_in_tile_number = int(1 << int.bit_length(
            _ceil_div(channels_in_align4/4, buffer_capacity))-1)

        channel_in_tile_size = int(channels_in_align4 /
                                   (channel_in_tile_number*split))

        # following is for model simulation debugging

        if (VALIDATE == True):
            valid = (channel_in_tile_number == self.Layer._ctrl_val_straddle)
            assert(valid), "straddle value not correct in layer {}, get {} but expecting {}.\n"\
                .format(self.Layer._layer_id, channel_in_tile_number,
                        self.Layer._ctrl_val_straddle)
            valid = (channel_in_tile_size ==
                     self.Layer._ctrl_val_compute_planes_align4)
            assert(valid), "computeplane value not correct in layer {}, get {} but expecting {}.\n"\
                .format(self.Layer._layer_id, channel_in_tile_size,
                        self.Layer._ctrl_val_compute_planes_align4)

        # store result in model instance
        self._compute_iter_length = channel_in_tile_size/4 * window_size_sqare
        self._window_size_square = window_size_sqare
        self._channel_in_tile_size = channel_in_tile_size
        self._channel_in_tile_number = channel_in_tile_number

    def get_channels_out_tile_size(self):
        """
        Compute the output depth(channel) tile size based on the estimated latency of LoadFeedingbuffer

        Required function call and pre-computed attributes or latency dictionary items:
            self.get_channels_in_tile_size():
                self._compute_iter_length
            self.get_LoadFeedingBuffer_latency():
                self._conversion_iter_number

        Generated dictionary items:
            self._row_step_number

        Generated IP attributes:
            self._pseudo_max_nkpf: a debugging result for simulation, need to be deleted
            self._channels_out_tile_size: the output depth tile size in computation, computed by nkpf*depth_per_nkpf (8 or 16 depending on _ker_factor)
            self._channels_out_tile_size_last: the last/remainder output depth tile size in computation, 
            self._channels_out_tile_number: the number of output tile
        """
        self._row_step_number = _ceil_div(
            self.Layer._output_height, self.Layer._row_step)

        # TODO: add group condition after alexnet is added

        max_nkpf = (self._weight_buffer_depth - 1) // self._compute_iter_length
        # max_nkpf = min(max_nkpf, 15)

        max_nkpf = min(max_nkpf, 15)
        min_nkpf = _ceil_div(self._conversion_iter_number,
                             self._compute_iter_length)
        if(min_nkpf > max_nkpf):
            max_nkpf = min_nkpf

        # set an assert here to make sure when new point is added, it need to report a problem
        assert(self._ker_factor in [8, 16, 24, 32]), "Invalid Ker factor of {}\n".format(
            self._ker_factor)

        if self._ker_factor in [32]:
            if max_nkpf * 16 > self.Layer._channels_out:
                max_nkpf = _ceil_div(self.Layer._channels_out, 16)
            if max_nkpf * 16 > self.Layer._channels_out:
                max_nkpf = max_nkpf - max_nkpf % 2

        if self._ker_factor in [24]:
            if max_nkpf * 24 > self.Layer._channels_out:
                max_nkpf = _ceil_div(self.Layer._channels_out, 24)

        elif self._ker_factor in [8, 16]:
            if self._ker_factor * max_nkpf > self.Layer._channels_out:
                max_nkpf = _ceil_div(
                    self.Layer._channels_out, self._ker_factor)
        else:
            AssertionError(
                "Invalid Ker factor of {}\n".format(self._ker_factor))

        if (VALIDATE == True):
            valid = (max_nkpf == self.Layer._ctrl_val_nkpf)
            assert(valid), "Nkpf value not correct in layer {}, get {} but expecting {}.\n"\
                .format(self.Layer._layer_id, max_nkpf,
                        self.Layer._ctrl_val_nkpf)

        if self._ker_factor in [16, 32]:
            depth_per_nkpf = 16
        elif self._ker_factor in [24]:
            depth_per_nkpf = 24
        elif self._ker_factor in [8]:
            depth_per_nkpf = 8
        else:
            AssertionError(
                "Invalid Ker factor of {}\n".format(self._ker_factor))

        # # FIXME: delete this line after the design is calibracated
        # self._pseudo_max_nkpf = max_nkpf

        # if (max_nkpf % 2 and max_nkpf != 1):
        #     max_nkpf = max_nkpf - 1

        channels_out_tile_size = max_nkpf * depth_per_nkpf
        channels_out_tile_number = _ceil_div(
            self.Layer._channels_out, channels_out_tile_size)
        if self.Layer._channels_out % channels_out_tile_size:
            channels_out_tile_size_last = self.Layer._channels_out % \
                channels_out_tile_size
        else:
            channels_out_tile_size_last = channels_out_tile_size

        self._channels_out_tile_size = channels_out_tile_size
        self._channels_out_tile_size_last = channels_out_tile_size_last
        self._channels_out_tile_number = channels_out_tile_number

        self._weight_one_time_flag = (
            self._channel_in_tile_number * self._channels_out_tile_number <= 2)
        self._latency_dict['_weight_one_time_flag'] = self._weight_one_time_flag

    def _update_remain_latency_by_real(self, task_remain_latency_dict, task_data_density_dict, real_latency_threashold, task_real_time_dict):
        accumulate_task_latency = 0
        remain_real_latency = real_latency_threashold
        total_density = sum(task_data_density_dict.values())
        pass_threshold_flag = False

        for key, value in sorted(task_remain_latency_dict.items(), key=lambda kv: kv[1]):

            if task_remain_latency_dict[key] == 0 or task_data_density_dict[key] == 0:
                total_density = total_density - task_data_density_dict[key]
                continue
            if pass_threshold_flag:
                if accumulate_task_latency > task_remain_latency_dict[key]:
                    AssertionError("accumulate_task_latency error")
                task_remain_latency_dict[key] -= accumulate_task_latency
                task_real_time_dict[key] += real_latency_threashold
                continue

            consumed_task_latency = task_remain_latency_dict[key] - \
                accumulate_task_latency

            consumed_real_latency = consumed_task_latency * total_density / \
                min(total_density, 1)

            if remain_real_latency < consumed_real_latency:
                consumed_latency = remain_real_latency * \
                    min(total_density, 1) / total_density
                remain_real_latency = 0
                accumulate_task_latency += consumed_latency
                pass_threshold_flag = True
            else:
                accumulate_task_latency = task_remain_latency_dict[key]
                remain_real_latency -= consumed_real_latency

            task_remain_latency_dict[key] -= accumulate_task_latency
            task_real_time_dict[key] += real_latency_threashold - \
                remain_real_latency
            total_density = total_density - task_data_density_dict[key]

    def _get_AXI_racing_latency_by_task(self, task_remain_latency_dict, task_data_density_dict, task_key, task_real_time_dict):
        """
        This function shall run AXI racing model until the AXI data task specified by task_key is over.
        task_remain_latency_dict: the dictionary that specify the remaining latency of each task, the function shall
                                update the remain latency of each task after the call.

        task_data_density_dict: the dictionay recording the data density through the latency. The data density is computed by
                                data ammount divided by total task latency.

        Return: the time between the starting of the remaining task and end of the specified task [task_key]
        """
        accumulate_task_latency = 0
        real_latency = 0
        total_density = sum(task_data_density_dict.values())
        pass_threshold_flag = False

        remaining_task_number = len(task_data_density_dict)

        for key, value in sorted(task_remain_latency_dict.items(), key=lambda kv: kv[1]):

            if task_remain_latency_dict[key] == 0 or task_data_density_dict[key] == 0:

                total_density = total_density - task_data_density_dict[key]
                if key == task_key:
                    pass_threshold_flag = True
                continue
            if pass_threshold_flag:
                if accumulate_task_latency > task_remain_latency_dict[key]:
                    AssertionError("accumulate_task_latency error")
                task_remain_latency_dict[key] -= accumulate_task_latency
                task_real_time_dict[key] = real_latency
                continue

            consumed_task_latency = task_remain_latency_dict[key] - \
                accumulate_task_latency

            consumed_real_latency = consumed_task_latency * total_density / \
                min(total_density, 1)

            remaining_task_number -= 1
            if key == task_key:
                pass_threshold_flag = True

            accumulate_task_latency = task_remain_latency_dict[key]
            real_latency += consumed_real_latency

            task_remain_latency_dict[key] -= accumulate_task_latency
            task_real_time_dict[key] += real_latency

            total_density = total_density - task_data_density_dict[key]

        return real_latency

    def _get_istg_latency(self, latency_key_read, latency_key_write, last_procweight_flag, first_row_step_flag):
        """
        latency_key_read: a string deciding whether to use first/normal/last read input latency information
        latency_key_write: a string deciding whether to use first/normal/last write input latency information
        last_procweight_flag: whether to normal/last procweight rowstep flag
        """
        if latency_key_read == 'ReadInputNormal':
            read_total_cycle = self._latency_dict['ReadInputNormal_Total']
            read_data_cycle = self._latency_dict['ReadInputNormal_Data']
        elif latency_key_read == 'ReadInputLast':
            read_total_cycle = self._latency_dict['ReadInputLast_Total']
            read_data_cycle = self._latency_dict['ReadInputLast_Data']
        elif latency_key_read == "None":
            read_total_cycle = 1
            read_data_cycle = 0
        else:
            AssertionError(
                "_get_istg_latency gets invalid latency_key_read as" + latency_key_write)

        if latency_key_write == 'WriteOutputNormal':
            write_total_cycle = self._latency_dict['WriteOutputNormal_Total']
            write_data_cycle = self._latency_dict['WriteOutputNormal_Data']
        elif latency_key_write == "None":
            write_total_cycle = 1
            write_data_cycle = 0
        else:
            AssertionError(
                "_get_istg_latency gets invalid latency_key_write as" + latency_key_write)

        proc_weight_overhead = self._latency_dict['ProcWeightOverhead']

        if last_procweight_flag == True:
            proc_weight_latency_normal_nkpf = self._latency_dict['ProcWeightLastRowStep']
            proc_weight_latency_last_nkpf = self._latency_dict['ProcWeightLast']
        else:
            proc_weight_latency_normal_nkpf = self._latency_dict['ProcWeightNormal']
            proc_weight_latency_last_nkpf = self._latency_dict['ProcWeightLastNkpf']

        data_time_stamp = 0
        compute_time_stamp = 0

        task_remain_latency_dict = {}
        task_data_density = {}
        task_real_time_dict = {}

        task_real_time_dict['weight'] = 0
        if(self._weight_one_time_flag and not first_row_step_flag):
            task_remain_latency_dict['weight'] = 0
            task_data_density['weight'] = 0
        else:
            task_remain_latency_dict['weight'] = self._latency_dict['LoadKern_Total']
            task_data_density['weight'] = self._latency_dict['LoadKern_Data'] / \
                self._latency_dict['LoadKern_Total']

        task_remain_latency_dict['readinput'] = read_total_cycle
        task_real_time_dict['readinput'] = 0
        task_data_density['readinput'] = read_data_cycle / \
            read_total_cycle if read_total_cycle else 0

        task_remain_latency_dict['writeoutput'] = write_total_cycle
        task_real_time_dict['writeoutput'] = 0
        task_data_density['writeoutput'] = write_data_cycle / \
            write_total_cycle if write_total_cycle else 0

        # compute first weight_load segment
        accumulate_real_latency = 0
        accumulate_data_latency = 0

        first_weight_load_latency = self._get_AXI_racing_latency_by_task(
            task_remain_latency_dict, task_data_density, 'weight', task_real_time_dict)
        accumulate_real_latency += first_weight_load_latency

        if first_row_step_flag:
            self._latency_dict['FirstWeightOverhead'] = accumulate_real_latency

        accumulate_data_latency += read_data_cycle
        accumulate_data_latency += write_data_cycle

        if not (self._weight_one_time_flag and not first_row_step_flag):
            accumulate_data_latency += self._latency_dict['LoadKern_Data']

        if first_weight_load_latency < proc_weight_overhead:
            real_latency = proc_weight_overhead - first_weight_load_latency
            self._update_remain_latency_by_real(
                task_remain_latency_dict, task_data_density, real_latency, task_real_time_dict)
            accumulate_real_latency += real_latency

        for input_tile_index in range(self._channel_in_tile_number):
            for output_tile_index in range(self._channels_out_tile_number):
                if output_tile_index == self._channels_out_tile_number - 1 and input_tile_index == self._channel_in_tile_number - 1:
                    break
                if self._weight_one_time_flag is False:
                    task_remain_latency_dict['weight'] = self._latency_dict['LoadKern_Total']
                    accumulate_data_latency += self._latency_dict['LoadKern_Data']

                if self._weight_one_time_flag is True and self._channel_in_tile_number*self._channels_out_tile_number == 2 and first_row_step_flag:
                    task_remain_latency_dict['weight'] = self._latency_dict['LoadKern_Total']
                    accumulate_data_latency += self._latency_dict['LoadKern_Data']

                weight_latency = self._get_AXI_racing_latency_by_task(
                    task_remain_latency_dict, task_data_density, 'weight', task_real_time_dict)

                accumulate_real_latency += weight_latency

                if output_tile_index < self._channels_out_tile_number - 1:
                    proc_weight_latency = proc_weight_latency_normal_nkpf
                else:
                    proc_weight_latency = proc_weight_latency_last_nkpf

                if weight_latency < proc_weight_latency:
                    real_latency = proc_weight_latency - weight_latency
                    self._update_remain_latency_by_real(
                        task_remain_latency_dict, task_data_density, real_latency, task_real_time_dict)
                    accumulate_real_latency += real_latency

        proc_weight_latency = proc_weight_latency_last_nkpf
        accumulate_real_latency += proc_weight_latency

        self._update_remain_latency_by_real(
            task_remain_latency_dict, task_data_density, proc_weight_latency, task_real_time_dict)

        max_key = max(task_remain_latency_dict,
                      key=lambda k: task_remain_latency_dict[k])

        left_over_communicate_latency = self._get_AXI_racing_latency_by_task(
            task_remain_latency_dict, task_data_density, max_key, task_real_time_dict)

        if(self._first_read_flag == True):
            self._latency_dict['FirstReadLatency'] = task_real_time_dict['readinput']
            self._first_read_flag = False
        accumulate_real_latency += left_over_communicate_latency

        return (accumulate_real_latency, accumulate_data_latency)

    def get_ProcIstg_latency(self):

        stage_type_table = {
            1: {'NoInput': ('None', 'None', True, True)},

            2: {'NoOutput': ('ReadInputLast', 'None', False, True),
                'NoInput': ('None', 'WriteOutputNormal', True, False)},

            3: {'NoOutput': ('ReadInputNormal', 'None', False, True),
                'LastInput': ('ReadInputLast', 'WriteOutputNormal', False, False),
                'NoInput': ('None', 'WriteOutputNormal', True, False)},

            4: {'NoOutput': ('ReadInputNormal', 'None', False, True),
                'NormalInput': ('ReadInputNormal', 'WriteOutputNormal', False, False),
                'LastInput': ('ReadInputLast', 'WriteOutputNormal', False, False),
                'NoInput': ('None', 'WriteOutputNormal', True, False)},
        }

        # start compute 4 stages of latency: NoOuput, NormalInput, LastInput, NoInput
        row_step_index = self._row_step_number if self._row_step_number < 4 else 4

        stage_latency_dict = {}
        for stage_tag in ['NoOutput', 'NormalInput', 'LastInput', 'NoInput']:
            if stage_tag in stage_type_table[row_step_index]:
                input_flag, output_flag, last_weight_flag, fist_row_step_flag = stage_type_table[
                    row_step_index][stage_tag]
                stage_latency_dict[stage_tag] = self._get_istg_latency(
                    input_flag, output_flag, last_weight_flag, fist_row_step_flag)
            else:
                stage_latency_dict[stage_tag] = (0, 0)

            self._latency_dict['Istage{}LatencyTotal'.format(
                stage_tag)] = stage_latency_dict[stage_tag][0]
            self._latency_dict['Istage{}LatencyData'.format(
                stage_tag)] = stage_latency_dict[stage_tag][1]

        self._latency_dict['IstageReadOverhead'] = self._latency_dict['ReadInputFirst_Total']
        self._latency_dict['IstageWriteOverhead'] = self._latency_dict['WriteOutputLast_Total']
        self._latency_dict['TotalLatency'] = self._latency_dict['IstageReadOverhead']\
            + self._latency_dict['IstageNoOutputLatencyTotal']\
            + self._latency_dict['IstageNormalInputLatencyTotal'] * (self._row_step_number - 3)\
            + self._latency_dict['IstageLastInputLatencyTotal']\
            + self._latency_dict['IstageNoInputLatencyTotal']\
            + self._latency_dict['WriteOutputLast_Total'] + \
            self._overall_overhead

    def get_LoadFeedingBuffer_latency(self):
        """
        Compute the latency of LoadFeedingBuffer 

        Required function call and pre-computed attributes or latency dictionary items:
            self.get_channels_in_tile_size():
                self._channel_in_tile_size
                self._window_size_square

        Generated dictionary items:
            self._latency_dict["LoadFeedingBuffer"] : the latency of LoadFeedingBuffer
        Generated IP attributes:
            self._conversion_iter_number: a approximated latency of LoadFeedingBuffer which is used to decide output tile size

        """

        conversion_number = _ceil_div(
            self._channel_in_tile_size/4, 16) * _ceil_div(self._pix_factor, 16)

        conversion_latency = 16 * self._window_size_square

        overhead_number = _ceil_div(conversion_number, 2)

        load_input_tile_latency = (
            conversion_number * conversion_latency +
            overhead_number * 15 + self.LOADFEEDINGBUFFER_OVERHEAD) *\
            self.CLK_PERIOD

        load_output_pixel_loacation_latency = self._pix_factor * self.CLK_PERIOD

        # FIXME: following result are just for modeling validation, need to fix and use computed latency
        conversion_iter_number = _ceil_div(self._channel_in_tile_size/4, 16) *\
            _ceil_div(self._pix_factor, 16) * self._window_size_square
        self._conversion_iter_number = conversion_iter_number

        window_size = self.Layer._window_size
        stride = self.Layer._stride

        load_input_tile_latency_first_layer = 2 * \
            (27 + window_size*(window_size+stride *
                               (self._pix_factor/2 - 1))) * self.CLK_PERIOD

        if self.Layer._layer_id == 0:
            self._latency_dict['LoadFeedingBuffer'] = load_input_tile_latency_first_layer + \
                load_output_pixel_loacation_latency
        else:
            self._latency_dict['LoadFeedingBuffer'] = load_input_tile_latency + \
                load_output_pixel_loacation_latency

    def get_ComputeKer16_latency(self):
        """
        Compute the latency of ComputeKer16 

        Required function call and pre-computed attributes or latency dictionary items:
            self.get_channels_in_tile_size():
                self._compute_iter_length
                self._window_size_square

        Generated dictionary items:
            self._latency_dict["ComputeKer16"] : the latency of ComputeKer16
        """

        compute_latency = (self._compute_iter_length+self._pix_factor/2 +
                           self.COMPUTEKER_OVERHEAD)*self.CLK_PERIOD

        self._latency_dict["ComputeKer16"] = compute_latency

    def get_OStgBuffSeq_latency(self):
        """
        Compute the latency of OStgBuffSeq function.

        Generated dictionary items:
            self._latency_dict["OStgBuffSeq"]: latency of OStgBuffSeq function 
        """
        self._latency_dict["OStgBuffSeq"] = (
            self._pix_factor + self.OSTGBUFFSEQ_OVERHEAD) * self.CLK_PERIOD

    def get_ProcResult_latency(self):
        """
        Compute the latency of ProcResult under different conditions

        Required function call and pre-computed attributes or latency dictionary items:
            self.get_channels_out_tile_size():
                self._channels_out_tile_size 
                self.__channels_out_tile_size_last
            self.get_ComputeKer16_latency():
                self._latency_dict["ComputeKer16"]
            self.get_OStgBuffSeq_latency()
                self._latency_dict["OStgBuffSeq"]

        Generated dictionary items:
            self._latency_dict["ProcResult"] : the latency of ProcResult with normal nkpf size
            self._latency_dict["ProcResultLast"] : the latency of ProcResult with last(remainder) nkpf size
        """

        self.get_ComputeKer16_latency()
        self.get_OStgBuffSeq_latency()
        self.get_channels_out_tile_size()
        ComputeKer16_latency = self._latency_dict["ComputeKer16"]
        OstgBuff_latency = self._latency_dict["OStgBuffSeq"]

        iteration_number = _ceil_div(
            self._channels_out_tile_size, self._ker_factor)
        iteration_number_last = _ceil_div(
            self._channels_out_tile_size_last, self._ker_factor)

        ProcResult_latency = self._pingpong_latency_helpler(
            ComputeKer16_latency, OstgBuff_latency, iteration_number)

        ProcResult_latency_last = self._pingpong_latency_helpler(
            ComputeKer16_latency, OstgBuff_latency, iteration_number_last)

        self._latency_dict["ProcResult"] = ProcResult_latency
        self._latency_dict["ProcResultLast"] = ProcResult_latency_last

    def get_WriteOutput_latency(self):
        """
        This function will compute different latency and data ammount to write output from DDR in each row step tile
        If self.Layer._mem_out is true. 
            It computes the latency and data latency simulating the behaviour of AXI mem interface
        Otherwise 
            It computes the latency and data latency simulating the behaviour of a FIFO

        Required function call and pre-computed attributes or latency dictionary items:
            None

        Following dictionay item in _latency_dict will be set:
            self._latency_dict['WriteOutputNormal_Data']
            self._latency_dict['WriteOutputNormal_Data']
            self._latency_dict['WriteOutputLast_Data']
            self._latency_dict['WriteOutputLast_Data']
        """
        output_depth = self.Layer._channels_out
        output_width = self.Layer._output_width
        output_height = self.Layer._output_height
        row_step = self.Layer._row_step

        output_height_normal = row_step * output_width
        burst_number = _ceil_div(output_depth, 32)

        if output_height % row_step:
            output_height_last = output_height % row_step
        else:
            output_height_last = row_step
        self._output_height_last = output_height_last
        if self.Layer._mem_out == True:
            total_cycle, data_cycle = self._mem_burst_write_latency(
                burst_number, row_step*output_width, 10)
            self._latency_dict['WriteOutputNormal_Data'] = data_cycle * \
                self.CLK_PERIOD
            self._latency_dict['WriteOutputNormal_Total'] = total_cycle * \
                self.CLK_PERIOD

            total_cycle, data_cycle = self._mem_burst_write_latency(
                burst_number, output_height_last*output_width, 10)
            self._latency_dict['WriteOutputLast_Data'] = data_cycle * \
                self.CLK_PERIOD
            self._latency_dict['WriteOutputLast_Total'] = total_cycle * \
                self.CLK_PERIOD
        else:
            self._latency_dict['WriteOutputNormal_Data'] = 0
            self._latency_dict['WriteOutputNormal_Total'] = burst_number * \
                row_step * output_width * self.CLK_PERIOD
            self._latency_dict['WriteOutputLast_Data'] = 0
            self._latency_dict['WriteOutputLast_Total'] = burst_number * \
                output_height_last * output_width * self.CLK_PERIOD

    def get_ReadInput_latency(self):
        """
        This function will compute different latency and data ammount to read input from DDR in each row step tile
        If self.Layer._mem_in is true. 
            It computes the latency and data latency simulating the behaviour of AXI mem interface
        Otherwise 
            It computes the latency and data latency simulating the behaviour of fifo

        Required function call and pre-computed attributes or latency dictionary items:
            None
        Following dictionay item in _latency_dict will be set:
            self._latency_dict['ReadInputFirst_Data'] 
            self._latency_dict['ReadInputFirst_Total'] 
            self._latency_dict['ReadInputNormal_Data']
            self._latency_dict['ReadInputNormal_Total']
            self._latency_dict['ReadInputLast_Data']
            self._latency_dict['ReadInputLast_Total']
        """

        input_depth = self.Layer._channels_in
        input_width = self.Layer._input_width
        input_height = self.Layer._input_height
        stride = self.Layer._stride
        filter_size = self.Layer._window_size
        pad_size = self.Layer._pad_size
        row_step = self.Layer._row_step

        if self._row_step_number == 1:
            input_height_first = input_height
            input_height_normal = 0
            input_height_last = 0
        else:
            input_height_first = (
                (row_step-1) * stride + filter_size) - pad_size
            if input_height_first > input_height:
                input_height_first = input_height

            input_height_normal = row_step * stride

            input_height_last = input_height - input_height_first - \
                input_height_normal*(self._row_step_number - 2)
            if input_height_last < 0:
                input_height_last = 0

        self._input_height_first = input_height_first
        self._input_height_last = input_height_last

        if self.Layer._layer_id == 0:
            assert(input_depth == 4), "First Layer depth not correct, get {} while expecting 4".format(
                input_depth)
            burst_number = _ceil_div(input_depth, 4)
        else:
            burst_number = _ceil_div(input_depth, 32)

        if self.Layer._mem_in == True:
            total_cycle, data_cycle = self._mem_burst_read_latency(
                burst_number, input_height_first*input_width, 10)
            self._latency_dict['ReadInputFirst_Data'] = data_cycle * \
                self.CLK_PERIOD
            self._latency_dict['ReadInputFirst_Total'] = total_cycle * \
                self.CLK_PERIOD

            total_cycle, data_cycle = self._mem_burst_read_latency(
                burst_number, input_height_normal*input_width, 10)
            self._latency_dict['ReadInputNormal_Data'] = data_cycle * \
                self.CLK_PERIOD
            self._latency_dict['ReadInputNormal_Total'] = total_cycle * \
                self.CLK_PERIOD

            total_cycle, data_cycle = self._mem_burst_read_latency(
                burst_number, input_height_last*input_width, 10)
            self._latency_dict['ReadInputLast_Data'] = data_cycle * \
                self.CLK_PERIOD
            self._latency_dict['ReadInputLast_Total'] = total_cycle * \
                self.CLK_PERIOD
        else:
            self._latency_dict['ReadInputFirst_Data'] = 0
            self._latency_dict['ReadInputFirst_Total'] = (
                10 + input_height_first * input_width * burst_number)*self.CLK_PERIOD
            self._latency_dict['ReadInputNormal_Data'] = 0
            self._latency_dict['ReadInputNormal_Total'] = (
                10 + input_height_normal * input_width * burst_number)*self.CLK_PERIOD
            self._latency_dict['ReadInputLast_Data'] = 0
            self._latency_dict['ReadInputLast_Total'] = (
                10 + input_height_last * input_width * burst_number)*self.CLK_PERIOD

    def get_LoadKer_latency(self):
        """
        This function will compute different latency and data ammount to read weight from DDR
        It computes the latency and data latency simulating the behaviour of AXI mem interface

        Required function call and pre-computed attributes or latency dictionary items:
            self.get_channels_out_tile_size():
                self._compute_iter_length 

        Following dictionay item in _latency_dict will be set:
            self._latency_dict["LoadKern_Data"] 
            self._latency_dict["LoadKern_Total"] 
        """

        if self._ker_factor in [16, 32]:
            depth_per_nkpf = 16
        elif self._ker_factor in [24]:
            depth_per_nkpf = 24
        elif self._ker_factor in [8]:
            depth_per_nkpf = 8
        else:
            AssertionError(
                "Invalid Ker factor of {}\n".format(self._ker_factor))

        # FIXME: currently it is usind _pseudo_max_nkpf, shoud be using read max_nkpf
        kernel_load_count = self._compute_iter_length * \
            self._channels_out_tile_size / depth_per_nkpf

        total_cycle, data_cycle = self._mem_burst_read_latency(
            1, kernel_load_count, 10)

        self._kernel_load_count = kernel_load_count
        self._latency_dict["LoadKern_Data"] = data_cycle * self.CLK_PERIOD
        self._latency_dict["LoadKern_Total"] = total_cycle * self.CLK_PERIOD

    def get_ProcWeight_latency(self):
        """
        Compute the latency of LoadFeedingBuffer 

        Required function call and pre-computed attributes or latency dictionary items:
            self.get_ProcResult_latency():
                self._latency_dict['ProcResult']
                self._latency_dict['ProcResultLast']
            self.get_LoadFeedingBuffer_latency():
                self._latency_dict['LoadFeedingBuffer']

        Generated dictionary items:
            self._latency_dict['ProcWeightNormal']
            self._latency_dict['ProcWeightLastNkpf']
            self._latency_dict['ProcWeightLastRowStep']
            self._latency_dict['ProcWeightLast']
            self._latency_dict['ProcWeightOverhead']

        """
        output_width = self.Layer._output_width
        output_height = self.Layer._output_height
        row_step = self.Layer._row_step
        if output_height % row_step:
            row_step_last = output_height % row_step
        else:
            row_step_last = row_step

        row_step_number = _ceil_div(output_height, row_step)
        output_pixel = output_width * row_step
        output_pixel_last = output_width * row_step_last

        pixel_factor_iters = _ceil_div(output_pixel, self._pix_factor)
        pixel_factor_iters_last = _ceil_div(
            output_pixel_last, self._pix_factor)

        ProcResult_latency = self._latency_dict['ProcResult']
        ProcResult_latency_last = self._latency_dict['ProcResultLast']

        LoadFeedingBuffer_latency = self._latency_dict['LoadFeedingBuffer']

        self._latency_dict['ProcWeightNormal'] = (pixel_factor_iters *
                                                  max(ProcResult_latency, LoadFeedingBuffer_latency))

        self._latency_dict['ProcWeightLastNkpf'] = ((pixel_factor_iters-1)*max(
            LoadFeedingBuffer_latency, ProcResult_latency_last)+ProcResult_latency_last)

        self._latency_dict['ProcWeightLastRowStep'] = (pixel_factor_iters_last *
                                                       max(ProcResult_latency, LoadFeedingBuffer_latency))

        self._latency_dict['ProcWeightLast'] = ((pixel_factor_iters_last-1)*max(
            LoadFeedingBuffer_latency, ProcResult_latency_last)+ProcResult_latency_last)

        self._latency_dict['ProcWeightOverhead'] = (
            self._latency_dict['LoadFeedingBuffer'])

    def write_latency_data_tab(self, file_pointer):
        file_pointer.write("{}".format(self.Layer._layer_id))
        for key, value in sorted(self._latency_dict.items(), key=lambda kv: kv[0]):
            file_pointer.write(",{},".format(value))
        file_pointer.write("\n")

    def write_latency_title_tab(self, file_pointer):
        file_pointer.write("layerID")
        for key, value in sorted(self._latency_dict.items(), key=lambda kv: kv[0]):
            file_pointer.write(",{},".format(key))
        file_pointer.write("\n")

    def get_latency(self):
        self.get_channels_in_tile_size()
        self.get_LoadFeedingBuffer_latency()
        self.get_ComputeKer16_latency()
        self.get_channels_out_tile_size()

        self.get_OStgBuffSeq_latency()
        self.get_ProcResult_latency()
        self.get_ProcWeight_latency()
        self.get_LoadKer_latency()

        self.get_ReadInput_latency()
        self.get_WriteOutput_latency()

        self.get_ProcIstg_latency()

    def initiate_input_rowstep(self):
        self._input_row_step_index = 0
        self._input_row_step = self.Layer._row_step * self.Layer._stride
        self._input_start_row = 0
        self._input_end_row = self._input_height_first - 1

    def increment_input_rowstep(self):
        self._input_row_step_index = self._input_row_step_index + 1

        assert(self._input_row_step_index <
               self._row_step_number), "loading input rowstep index out of boundary"
        self._input_start_row = self._input_end_row + 1

        if self._output_row_step_index == self._row_step_number - 1:
            self._input_end_row = self._input_start_row + self._input_height_last - 1
        else:
            self._input_end_row = self._input_start_row + self._input_row_step - 1

    def initiate_output_rowstep(self):
        self._output_row_step_index = 0
        self._output_row_step = self.Layer._row_step
        self._output_start_row = 0
        self._output_end_row = self._output_row_step - 1

    def increment_output_rowstep(self):
        self._output_row_step_index = self._output_row_step_index + 1
        assert(self._output_row_step_index <
               self._row_step_number), "loading output rowstep index out of boundary"
        self._output_start_row = self._output_end_row + 1
        if self._output_row_step_index == self._row_step_number - 1:
            self._output_end_row = self._output_start_row + self._output_height_last - 1
        else:
            self._output_end_row = self._output_start_row + self._output_row_step - 1

    def get_phase_list(self):
        phast_lsit = []

        first_row_step = self._input_height_first - 1

        # initialize start and end row recorder for rowstep

        output_row_step = self.Layer._row_step

        self.initiate_input_rowstep()
        self.initiate_output_rowstep()

        # pre phase
        phase_pre = Phase()
        phase_pre.set_latency_info(
            self._latency_dict['ReadInputFirst_Data'],
            self._latency_dict['ReadInputFirst_Data'],
            self._latency_dict['ReadInputFirst_Total'])

        if self.Layer._mem_in:
            phase_pre.set_read_row_info(None, None)
        else:
            phase_pre.set_read_row_info(
                self._input_start_row, self._input_end_row)

        phase_pre.set_write_row_info(None, None)
        phast_lsit.append(phase_pre)

        # no output phase
        if self._row_step_number >= 2:
            self.increment_input_rowstep()
            phase_nooutput = Phase()
            phase_nooutput.set_latency_info(
                self._latency_dict['IstageNoOutputLatencyData'],
                self._latency_dict['IstageNoOutputLatencyData'],
                self._latency_dict['IstageNoOutputLatencyTotal'])
            if self.Layer._mem_in:
                phase_nooutput.set_read_row_info(None, None)
            else:
                phase_nooutput.set_read_row_info(
                    self._input_start_row, self._input_end_row)
            phase_nooutput.set_write_row_info(None, None)

            phast_lsit.append(phase_nooutput)

        # normalinput phase

        if self._row_step_number >= 4:
            for i in range(self._row_step_number - 3):
                self.increment_input_rowstep()
                self.increment_output_rowstep()
                phase_normalinput = Phase()
                phase_normalinput.set_latency_info(
                    self._latency_dict['IstageNormalInputLatencyData'],
                    self._latency_dict['IstageNormalInputLatencyData'],
                    self._latency_dict['IstageNormalInputLatencyTotal'])
                if self.Layer._mem_in:
                    phase_normalinput.set_read_row_info(None, None)
                else:
                    phase_normalinput.set_read_row_info(
                        self._input_start_row, self._input_end_row)
                if self.Layer._mem_out:
                    phase_normalinput.set_write_row_info(None, None)
                else:
                    phase_normalinput.set_write_row_info(
                        self._output_start_row, self._output_end_row)

                phast_lsit.append(phase_normalinput)

        # LastInput phase
        if self._row_step_number >= 3:
            self.increment_input_rowstep()
            self.increment_output_rowstep()
            phase_LastInput = Phase()
            phase_LastInput.set_latency_info(
                self._latency_dict['IstageLastInputLatencyData'],
                self._latency_dict['IstageLastInputLatencyData'],
                self._latency_dict['IstageLastInputLatencyTotal'])
            if self.Layer._mem_in:
                phase_LastInput.set_read_row_info(None, None)
            else:
                phase_LastInput.set_read_row_info(
                    self._input_start_row, self._input_end_row)
            if self.Layer._mem_out:
                phase_LastInput.set_write_row_info(None, None)
            else:
                phase_LastInput.set_write_row_info(
                    self._output_start_row, self._output_end_row)

            phast_lsit.append(phase_LastInput)

        # noinput phase
        if self._row_step_number >= 1:
            self.increment_output_rowstep()
            phase_NoInput = Phase()
            phase_NoInput.set_latency_info(
                self._latency_dict['IstageNoInputLatencyData'],
                self._latency_dict['IstageNoInputLatencyData'],
                self._latency_dict['IstageNoInputLatencyTotal'])

            phase_NoInput.set_read_row_info(None, None)
            if self.Layer._mem_out:
                phase_NoInput.set_write_row_info(None, None)
            else:
                phase_NoInput.set_write_row_info(
                    self._output_start_row, self._output_end_row)

            phast_lsit.append(phase_NoInput)

        # post phase
        self.increment_output_rowstep()
        phase_Post = Phase()
        phase_Post.set_latency_info(
            self._latency_dict['IstagePostLatencyData'],
            self._latency_dict['IstagePostLatencyData'],
            self._latency_dict['IstagePostLatencyTotal'])

        phase_Post.set_read_row_info(None, None)
        if self.Layer._mem_out:
            phase_Post.set_write_row_info(None, None)
        else:
            phase_Post.set_write_row_info(
                self._output_start_row, self._output_end_row)

        phast_lsit.append(phase_Post)

        assert(self._input_row_step_index == self._row_step_number -
               1), "input row step number not matching row step number, expecting {} but geting {}".format(
                self._input_row_step_index, self._row_step_number)

        assert(self._output_row_step_index == self._row_step_number -
               1), "output row step number not matching row step number, expecting {} but geting {}".format(
                self._output_row_step_index, self._row_step_number)



class PoolIP():
    def load_layerInfo(self, layerInfo):
        self.layerInfo = layerInfo

    def get_latency(self):
        return None

    def PreDataCycle0():
        return 0

    def PreDataCycle1():
        return 0

    def PreTotalCycle():
        return 0

    def RecurDataCycleFirst0():
        return 0

    def RecurDataCycleFirst1():
        return 0

    def RecurTotalCycleFirst():
        return 0

    def RecurDataCycleMid0():
        return 0

    def RecurDataCycleMid1():
        return 0

    def RecurTotalCycleMid():
        return 0

    def RecurDataCycleSecondLast0():
        return 0

    def RecurDataCycleSecondLast1():
        return 0

    def RecurTotalCycleSecondLast():
        return 0

    def RecurDataCycleLast0():
        return 0

    def RecurDataCycleLast1():
        return 0

    def RecurTotalCycleLast():
        return 0

    def PostDataCycle0():
        return 0

    def PostDataCycle1():
        return 0

    def PostTotalCycle():
        return 0

    def RowNum():
        return 0

    def RowStep():
        return 0

    def DepsRowStepFirst():
        return 0

    def DepsRowStepRecur():
        return 0

    def LastStartRow():
        return 0

    def SecondLastStartRow():
        return 0

    def Stride():
        return 0


class EltIP():
    def __init__(self, input_depth):
        self._input_buffer_depth = input_depth
        self.AXI_ACK_CYCLE = 3.5
        self.AXI_RESPONSE_CYCLE = 24
        self.AXI_ACK_CYCLE_WRITE = 7
        self.AXI_RESPONSE_CYCLE_WRITE = 40
        self.CLK_PERIOD = 4.0
        self._latency_dict = {}

    def load_layer(self, Layer):
        self.Layer = Layer

    def _mem_burst_read_latency(self, burst_number, burst_length, burst_overhead):
        """
        computes the function latency and bandwidth latency of a sequence of burstReads
        return: totalCycle: the total cycle number such sequence of burst read takes
                dataCycle: the total cycle number for data transfer such sequence of burst read takes ( it will be in conflict with other read)
        input burstNumber: the number of burst read in the burst sequence
        input burstLength: the length of each burst read
        input burstOverhead: the cycle number between the time last burst read data is receive till the start of issurance of next burst read
        """
        if(burst_length == 0):
            return 0, 0
        burst_breaks = _ceil_div(burst_length, 16)

        data_cycle = (burst_length+burst_breaks *
                      self.AXI_ACK_CYCLE)*burst_number

        total_cycle = (burst_overhead + self.AXI_RESPONSE_CYCLE) * \
            burst_number + data_cycle

        return total_cycle, data_cycle

    def _mem_burst_write_latency(self, burst_number, burst_length, burst_overhead):
        """
        computes the function latency and bandwidth latency of a sequence of burstReads
        return: totalCycle: the total cycle number such sequence of burst read takes
                dataCycle: the total cycle number for data transfer such sequence of burst read takes ( it will be in conflict with other read)
        input burstNumber: the number of burst read in the burst sequence
        input burstLength: the length of each burst read
        input burstOverhead: the cycle number between the time last burst read data is receive till the start of issurance of next burst read
        """
        if(burst_length == 0):
            return 0, 0
        burst_breaks = _ceil_div(burst_length, 16)

        data_cycle = (burst_length+(burst_breaks-1) *
                      self.AXI_ACK_CYCLE_WRITE)*burst_number

        if(burst_breaks == 1):
            responseoffset = -5
        else:
            responseoffset = 0

        total_cycle = (burst_overhead + self.AXI_RESPONSE_CYCLE_WRITE+responseoffset) * \
            burst_number + data_cycle

        return total_cycle, data_cycle

    def _update_remain_latency_by_real(self, task_remain_latency_dict, task_data_density_dict, real_latency_threashold, task_real_time_dict):
        accumulate_task_latency = 0
        remain_real_latency = real_latency_threashold
        total_density = sum(task_data_density_dict.values())
        pass_threshold_flag = False

        for key, value in sorted(task_remain_latency_dict.items(), key=lambda kv: kv[1]):

            if task_remain_latency_dict[key] == 0 or task_data_density_dict[key] == 0:
                total_density = total_density - task_data_density_dict[key]
                continue
            if pass_threshold_flag:
                if accumulate_task_latency > task_remain_latency_dict[key]:
                    AssertionError("accumulate_task_latency error")
                task_remain_latency_dict[key] -= accumulate_task_latency
                task_real_time_dict[key] += real_latency_threashold
                continue

            consumed_task_latency = task_remain_latency_dict[key] - \
                accumulate_task_latency

            consumed_real_latency = consumed_task_latency * total_density / \
                min(total_density, 1)

            if remain_real_latency < consumed_real_latency:
                consumed_latency = remain_real_latency * \
                    min(total_density, 1) / total_density
                remain_real_latency = 0
                accumulate_task_latency += consumed_latency
                pass_threshold_flag = True
            else:
                accumulate_task_latency = task_remain_latency_dict[key]
                remain_real_latency -= consumed_real_latency

            task_remain_latency_dict[key] -= accumulate_task_latency
            task_real_time_dict[key] += real_latency_threashold - \
                remain_real_latency
            total_density = total_density - task_data_density_dict[key]

    def _get_AXI_racing_latency_by_task(self, task_remain_latency_dict, task_data_density_dict, task_key, task_real_time_dict):
        """
        This function shall run AXI racing model until the AXI data task specified by task_key is over.
        task_remain_latency_dict: the dictionary that specify the remaining latency of each task, the function shall
                                update the remain latency of each task after the call.

        task_data_density_dict: the dictionay recording the data density through the latency. The data density is computed by
                                data ammount divided by total task latency.

        Return: the time between the starting of the remaining task and end of the specified task [task_key]
        """
        accumulate_task_latency = 0
        real_latency = 0
        total_density = sum(task_data_density_dict.values())
        pass_threshold_flag = False

        remaining_task_number = len(task_data_density_dict)

        for key, value in sorted(task_remain_latency_dict.items(), key=lambda kv: kv[1]):

            if task_remain_latency_dict[key] == 0 or task_data_density_dict[key] == 0:

                total_density = total_density - task_data_density_dict[key]
                if key == task_key:
                    pass_threshold_flag = True
                continue
            if pass_threshold_flag:
                if accumulate_task_latency > task_remain_latency_dict[key]:
                    AssertionError("accumulate_task_latency error")
                task_remain_latency_dict[key] -= accumulate_task_latency
                task_real_time_dict[key] = real_latency
                continue

            consumed_task_latency = task_remain_latency_dict[key] - \
                accumulate_task_latency

            consumed_real_latency = consumed_task_latency * total_density / \
                min(total_density, 1)

            remaining_task_number -= 1
            if key == task_key:
                pass_threshold_flag = True

            accumulate_task_latency = task_remain_latency_dict[key]
            real_latency += consumed_real_latency

            task_remain_latency_dict[key] -= accumulate_task_latency
            task_real_time_dict[key] += real_latency

            total_density = total_density - task_data_density_dict[key]

        return real_latency

    def get_read_lateney(self):
        input_height = self.Layer._input_height
        input_width = self.Layer._input_width
        input_depth = self.Layer._channels_in
        row_step = self.Layer._row_step

        row_step_last = input_height % row_step if input_height % row_step != 0 else row_step
        burst_number = _ceil_div(input_depth, 16)
        burst_length = input_width * row_step
        burst_length_last = input_width * row_step_last

        total_cycle, data_cycle = self._mem_burst_read_latency(
            burst_number, burst_length, 10)
        self._latency_dict['ReadLeftNormal_Total'] = total_cycle * \
            self.CLK_PERIOD
        self._latency_dict['ReadLeftNormal_Data'] = data_cycle * \
            self.CLK_PERIOD

        total_cycle, data_cycle = self._mem_burst_read_latency(
            burst_number, burst_length_last, 10)
        self._latency_dict['ReadLeftLast_Total'] = total_cycle * \
            self.CLK_PERIOD
        self._latency_dict['ReadLeftLast_Data'] = data_cycle * \
            self.CLK_PERIOD

    def get_write_lateney(self):
        output_height = self.Layer._output_height
        output_width = self.Layer._output_width
        output_depth = self.Layer._channels_out
        row_step = self.Layer._row_step

        row_step_last = output_height % row_step if output_height % row_step != 0 else row_step
        self._row_step_last = row_step_last
        burst_number = _ceil_div(output_depth, 16)
        burst_length = output_width * row_step
        burst_length_last = output_width * row_step_last

        total_cycle, data_cycle = self._mem_burst_write_latency(
            burst_number, burst_length, 10)
        self._latency_dict['WriteOutputNormal_Total'] = total_cycle * \
            self.CLK_PERIOD
        self._latency_dict['WriteOutputNormal_Data'] = data_cycle * \
            self.CLK_PERIOD

        total_cycle, data_cycle = self._mem_burst_write_latency(
            burst_number, burst_length_last, 10)
        self._latency_dict['WriteOutputLast_Total'] = total_cycle * \
            self.CLK_PERIOD
        self._latency_dict['WriteOutputLast_Data'] = data_cycle * \
            self.CLK_PERIOD

    def get_phase_latency(self):
        row_step = self.Layer._row_step
        input_height = self.Layer._input_height
        row_step_number = _ceil_div(input_height, row_step)

        # process ovehead phase
        self._latency_dict['ReadInputOverhead_Data'] = self._latency_dict['ReadLeftNormal_Data']
        self._latency_dict['ReadInputOverhead_Total'] = self._latency_dict['ReadLeftNormal_Total']

        self._row_step_number = row_step_number
        # process normal read, normal write
        if row_step_number > 2:
            self._latency_dict['NormalPhase_Total'] = max(
                self._latency_dict['ReadLeftNormal_Total'], self._latency_dict['WriteOutputNormal_Total'])
        else:
            self._latency_dict['NormalPhase_Total'] = 0

        # process Last read, normal write
        if row_step_number > 1:
            self._latency_dict['LastPhase_Total'] = max(
                self._latency_dict['ReadLeftLast_Total'], self._latency_dict['WriteOutputNormal_Total'])
        else:
            self._latency_dict['LastPhase_Total'] = 0

        # write overhead

        self._latency_dict['WriteOutputOverhead_Data'] = self._latency_dict['WriteOutputLast_Data']
        self._latency_dict['WriteOutputOverhead_Total'] = self._latency_dict['WriteOutputLast_Total']

        self._latency_dict['TotalLatency'] = self._latency_dict['ReadInputOverhead_Data'] + \
            self._latency_dict['WriteOutputOverhead_Total'] + \
            self._latency_dict['LastPhase_Total'] + \
            self._latency_dict['NormalPhase_Total'] * (row_step_number - 2)

    def get_latency(self):
        self.get_read_lateney()
        self.get_write_lateney()
        self.get_phase_latency()

    def write_latency_data_tab(self, file_pointer):
        file_pointer.write("{}".format(self.Layer._layer_id))
        for key, value in sorted(self._latency_dict.items(), key=lambda kv: kv[0]):
            file_pointer.write(",{},".format(value))
        file_pointer.write("\n")

    def write_latency_title_tab(self, file_pointer):
        file_pointer.write("layerID")
        for key, value in sorted(self._latency_dict.items(), key=lambda kv: kv[0]):
            file_pointer.write(",{},".format(key))
        file_pointer.write("\n")

    def load_layerInfo(self, layerInfo):
        self.layerInfo = layerInfo


    def initiate_input_rowstep(self):
        self._input_row_step_index = 0
        self._input_row_step = self.Layer._row_step
        self._input_start_row = 0
        self._input_end_row = self._input_row_step - 1

    def increment_input_rowstep(self):
        self._input_row_step_index = self._input_row_step_index + 1

        assert(self._input_row_step_index <
               self._row_step_number), "loading input rowstep index out of boundary"

        self._input_start_row = self._input_end_row + 1

        if self._output_row_step_index == self._row_step_number - 1:
            self._input_end_row = self._input_start_row + self._row_step_last - 1
        else:
            self._input_end_row = self._input_start_row + self._input_row_step - 1

    def initiate_output_rowstep(self):
        self._output_row_step_index = 0
        self._output_row_step = self.Layer._row_step
        self._output_start_row = 0
        self._output_end_row = self._output_row_step - 1

    def increment_output_rowstep(self):
        self._output_row_step_index = self._output_row_step_index + 1
        assert(self._output_row_step_index <
               self._row_step_number), "loading output rowstep index out of boundary"
        self._output_start_row = self._output_end_row + 1
        if self._output_row_step_index == self._row_step_number - 1:
            self._output_end_row = self._output_start_row + self._row_step_last - 1
        else:
            self._output_end_row = self._output_start_row + self._output_row_step - 1
    

    def get_phase_list(self):
        phast_lsit = []


        # initialize start and end row recorder for rowstep

     

        self.initiate_input_rowstep()
        self.initiate_output_rowstep()

        # pre phase
        phase_pre = Phase()
        phase_pre.set_latency_info(
            self._latency_dict['ReadInputNormal_Data'],
            0,
            self._latency_dict['ReadInputNormal_Total'])

        if self.Layer._mem_in:
            phase_pre.set_read_row_info(None, None)
        else:
            phase_pre.set_read_row_info(
                self._input_start_row, self._input_end_row)

        phase_pre.set_write_row_info(None, None)
        phast_lsit.append(phase_pre)

        # normalinput phase
        if self._row_step_number >= 3:
            for i in range(self._row_step_number - 2):
                self.increment_input_rowstep()
                self.increment_output_rowstep()
                phase_normalinput = Phase()
                phase_normalinput.set_latency_info(
                    self._latency_dict['ReadLeftNormal_Data'],
                    self._latency_dict['WriteOutputNormal_Data'],
                    self._latency_dict['NormalPhase_Total'])
                if self.Layer._mem_in:
                    phase_normalinput.set_read_row_info(None, None)
                else:
                    phase_normalinput.set_read_row_info(
                        self._input_start_row, self._input_end_row)
                if self.Layer._mem_out:
                    phase_normalinput.set_write_row_info(None, None)
                else:
                    phase_normalinput.set_write_row_info(
                        self._output_start_row, self._output_end_row)

                phast_lsit.append(phase_normalinput)

        # LastInput phase
        if self._row_step_number >= 2:
            self.increment_input_rowstep()
            self.increment_output_rowstep()
            phase_LastInput = Phase()
            phase_LastInput.set_latency_info(
                self._latency_dict['ReadLeftLast_Total'],
                self._latency_dict['WriteOutputNormal_Data'],
                self._latency_dict['LastPhase_Total'])
            if self.Layer._mem_in:
                phase_LastInput.set_read_row_info(None, None)
            else:
                phase_LastInput.set_read_row_info(
                    self._input_start_row, self._input_end_row)
            if self.Layer._mem_out:
                phase_LastInput.set_write_row_info(None, None)
            else:
                phase_LastInput.set_write_row_info(
                    self._output_start_row, self._output_end_row)

            phast_lsit.append(phase_LastInput)


        # post phase
        self.increment_output_rowstep()
        phase_Post = Phase()
        phase_Post.set_latency_info(
                0,
                self._latency_dict['WriteOutputLast_Data'],
                self._latency_dict['WriteOutputLast_Total'])

        phase_Post.set_read_row_info(None, None)
        if self.Layer._mem_out:
            phase_Post.set_write_row_info(None, None)
        else:
            phase_Post.set_write_row_info(
                self._output_start_row, self._output_end_row)

        phast_lsit.append(phase_Post)

        assert(self._input_row_step_index == self._row_step_number -
               1), "input row step number not matching row step number, expecting {} but geting {}".format(
                self._input_row_step_index, self._row_step_number)

        assert(self._output_row_step_index == self._row_step_number -
               1), "output row step number not matching row step number, expecting {} but geting {}".format(
                self._output_row_step_index, self._row_step_number)



class ConvLayerInfo():

    def __init__(self):
        self._feeding_buffer_size = 1024

    def set_from_layerInfo(self, layerInfo):
        self._input_height = layerInfo.inp_height
        self._input_width = layerInfo.inp_width
        self._output_height = layerInfo.out_height
        self._output_width = layerInfo.out_width
        self._channels_out = layerInfo.out_planes
        self._channels_in = layerInfo.inp_planes
        self._stride = layerInfo.stride
        self._pad_size = layerInfo.pad
        w_h = layerInfo.filter_height
        w_w = layerInfo.filter_width
        assert(w_h == w_w), "the window size is not square"
        self._window_size = w_h
        self._layer_id = layerInfo.layerID
        self._row_step = layerInfo.rowStep
        self._mem_in = layerInfo.memIn
        self._mem_out = layerInfo.mode

    def set_from_file(self, file_name):
        args_file = open(file_name, 'rb')
        args_list = []
        for i in range(128):
            args_list.append(struct.unpack('i', args_file.read(4))[0])
        self._args_list = args_list
        self._input_height = args_list[0]
        self._input_width = args_list[1]
        self._output_height = args_list[2]
        self._output_width = args_list[3]
        self._channels_out = args_list[4]
        self._channels_in = args_list[5]
        self._stride = args_list[6]
        self._pad_size = args_list[9]
        w_h = args_list[7]
        w_w = args_list[8]
        assert(w_h == w_w), "the window size is not square"
        self._window_size = w_h
        self._layer_id = args_list[12]
        self._row_step = args_list[15]
        self._mem_in = True
        self._mem_out = True

        self._ctrl_val_nkpf = args_list[13]
        self._ctrl_val_compute_planes_align4 = args_list[61]
        self._ctrl_val_straddle = args_list[17]
        self._group_number = 1

    def set_from_node(self, file_name, node_data, layer_id, group_flag):

        self._input_height = node_data._input_height
        self._input_width = node_data._input_width
        self._output_height = node_data._output_height
        self._output_width = node_data._output_width
        self._channels_out = node_data._channels_out
        self._channels_in = node_data._channels_in
        self._stride = node_data._stride
        self._window_size = node_data._window_size
        if(node_data._pad == 'VALID'):
            self._pad_size = int(self._window_size/2)
        if group_flag == 0:
            self._group_number = 1
        else:
            self._group_number = 2


def constantBramConv(wBufferSize, ker_proc, pix_proc):
    # need validation
    if ker_proc == 32:
        ker_proc = 16

    wBrams = math.ceil(wBufferSize / 1024.0) * \
        ker_proc * math.ceil(32.0/18) * 2
    feedingBrams = 2 * math.ceil(32.0/18) * pix_proc/2 * 2
    resulting = 2*ker_proc * 2 * 2
    bias_scale = 24
    brams = wBrams + feedingBrams + resulting + bias_scale
    return brams


def computeIOBram(IN_D, OUT_D):
    inBrams = 2*_ceil_div(IN_D, 1024) * 8 * 2 * math.ceil(32.0/18)
    outBrams = 2*_ceil_div(OUT_D, 1024) * 8 * math.ceil(72.0/18) * 2
    # print  [inBrams, outBrams]
    return [inBrams, outBrams]


def computeRequiredIODepth(layerInfo, rowStep):

    conv_out_planes = layerInfo._channels_out
    conv_inp_planes = layerInfo._channels_in
    conv_stride = layerInfo._stride
    conv_inp_width = layerInfo._input_width
    conv_out_width = layerInfo._output_width
    conv_filter_height = layerInfo._window_size
    layerID = layerInfo._layer_id

    if(layerID != 0):
        IN_D = 1 << int.bit_length(
            conv_inp_width * (-(-conv_inp_planes//64))*(conv_filter_height+(rowStep*2-1)*conv_stride))
    else:
        IN_D = 1024
    IN_D = max(IN_D, 1024)
    OUT_D = _align_size(
        int(conv_out_width*_ceil_div(conv_out_planes, 32)*rowStep), 1024)
    return [IN_D, OUT_D]


def main_conv_brutal_search():
    global VALIDATE
    VALIDATE = 0
    parser = argparse.ArgumentParser(
        description='Please Specify BRAM for conv layer')
    parser.add_argument('-bram', type=int, help="number of BRAM")
    parser.add_argument('-argsfolder', type=str,
                        help="folder containing args files")
    args = parser.parse_args()

    folder_name = args.argsfolder
    bram_budget = args.bram

    deposit_all_layer_latency = float('inf')
    deposit_ip_configure = None
    deposit_all_layer_row_step = {}

    for weight_depth in [1024, 2048, 3072, 4096]:
        for input_depth in [1024, 2048, 4096, 8192]:
            for output_depth in [1024, 2048, 3072, 4096]:
                for ker_factor in [8, 16, 32]:
                    for pix_factor in [16, 32, 48]:
                        if ker_factor*pix_factor > 800:
                            continue
                        total_bram = constantBramConv(weight_depth, ker_factor, pix_factor) \
                            + sum(computeIOBram(input_depth, output_depth))
                        if total_bram > bram_budget:
                            continue

                        row_step_list = {}
                        IP_valid_flag = True
                        layer_latency_list = []

                        for i in range(77):
                            args_file_name = folder_name+"/args_conv_L"+str(i)

                            if not os.path.exists(args_file_name):
                                continue

                            conv_layer = ConvLayerInfo()
                            conv_layer.set_from_file(args_file_name)

                            deposit_layer_latency = float('inf')
                            deposit_row_step = None

                            for row_step in range(1, conv_layer._output_height+1):

                                required_input_depth, required_output_depth = computeRequiredIODepth(
                                    conv_layer, row_step)
                                if required_input_depth > input_depth or required_output_depth > output_depth:
                                    break
                                conv_layer._row_step = row_step
                                test_IP = ConvIP(
                                    ConvIP, ker_factor, pix_factor, input_depth, output_depth, weight_depth)
                                test_IP.load_layer(conv_layer)
                                test_IP.get_latency()

                                layer_latency = test_IP._latency_dict['TotalLatency']
                                if layer_latency < deposit_layer_latency:
                                    deposit_layer_latency = layer_latency
                                    deposit_row_step = row_step

                            if deposit_row_step == None:
                                IP_valid_flag = False
                                break
                            layer_latency_list.append(deposit_layer_latency)
                            row_step_list[conv_layer._layer_id] = deposit_row_step

                        all_layer_latency = sum(layer_latency_list)
                        if all_layer_latency < deposit_all_layer_latency:
                            deposit_all_layer_latency = all_layer_latency
                            deposit_all_layer_row_step = row_step_list
                            deposit_ip_configure = (
                                ker_factor, pix_factor, input_depth, output_depth, weight_depth)
    print(deposit_ip_configure)
    print(deposit_all_layer_latency)
    print(deposit_all_layer_row_step)

    for key, value in deposit_all_layer_row_step.items():
        print(key, end=',')
        print(value)


def validate_one_conv_IP():
    global VALIDATE
    VALIDATE = 1
    parser = argparse.ArgumentParser(
        description='Please Specify BRAM for conv layer')
    parser.add_argument('-bram', type=int, help="number of BRAM")
    parser.add_argument('-argsfolder', type=str,
                        help="folder containing args files")
    args = parser.parse_args()

    folder_name = args.argsfolder

    csv_file = open("model_latency.csv", "w")
    for i in range(77):
        args_file_name = folder_name+"/args_conv_L"+str(i)

        if os.path.exists(args_file_name):
            conv_layer = ConvLayerInfo()
            conv_layer.set_from_file(args_file_name)
            test_IP = ConvIP(ConvIP, 16, 48, 4096, 4096, 2048)
            test_IP.load_layer(conv_layer)
            test_IP.get_latency()

            pp = pprint.PrettyPrinter(indent=4)
            pp.pprint(test_IP._latency_dict)
            if(i == 0):
                test_IP.write_latency_title_tab(csv_file)
            test_IP.write_latency_data_tab(csv_file)


def validate_one_elt_IP():
    global VALIDATE
    VALIDATE = 1

    layer_config = [
        (56, 56, 256, 4),
        (28, 28, 512, 4),
        (14, 14, 1024, 4),
        (7, 7, 2048, 4),
        (56, 56, 256, 3),
        (28, 28, 512, 3),
        (14, 14, 1024, 3),
        (7, 7, 2048, 3),
        (56, 56, 256, 2),
        (28, 28, 512, 2),
        (14, 14, 1024, 2),
        (7, 7, 2048, 2),
        (56, 56, 256, 1),
        (28, 28, 512, 1),
        (14, 14, 1024, 1),
        (7, 7, 2048, 1)]

    csv_file = open("model_latency.csv", "w")

    for i, layer in enumerate(layer_config):
        layer_info = ConvLayerInfo()
        layer_info._input_height = layer[0]
        layer_info._output_height = layer[0]
        layer_info._input_width = layer[1]
        layer_info._output_width = layer[1]
        layer_info._channels_in = layer[2]
        layer_info._channels_out = layer[2]
        layer_info._row_step = layer[3]
        layer_info._layer_id = i
        test_IP = EltIP(8192)
        test_IP.load_layer(layer_info)
        test_IP.get_latency()
        if(i == 0):
            test_IP.write_latency_title_tab(csv_file)
        test_IP.write_latency_data_tab(csv_file)


if __name__ == "__main__":
    # validate_one_IP()
    # main_conv_brutal_search()
    validate_one_elt_IP()
