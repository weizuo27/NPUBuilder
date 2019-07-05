import os.path
import struct
import sys
import pprint
VALIDATE = 1


def _align_size(x, y):
    return -int(-x//y)*y


def _ceil_div(x, y):
    """
    Cell division

    """
    return -int(-x//y)


class ConvIP():
    ker_factor_list = [0, 8, 16, 32]
    pix_factor_list = [0, 8, 16, 32, 48]

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
        self.AXI_RESPONSE_CYCLE = 26
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
        self._row_step_number = _ceil_div(self.Layer._output_height, self.Layer._row_step)

        # TODO: add group condition after alexnet is added

        max_nkpf = (self._weight_buffer_depth - 1) // self._compute_iter_length
        max_nkpf = min(max_nkpf, 15)
        min_nkpf = _ceil_div(self._conversion_iter_number,
                             self._compute_iter_length)
        if(min_nkpf > max_nkpf):
            max_nkpf = min_nkpf

        # set an assert here to make sure when new point is added, it need to report a problem
        assert(self._ker_factor in [8, 16, 32]), "Invalid Ker factor of {}\n".format(
            self._ker_factor)

        if self._ker_factor in [32]:
            if max_nkpf * 16 > self.Layer._channels_out:
                max_nkpf = _ceil_div(self.Layer._channels_out, 16)
            if max_nkpf * 16 < self.Layer._channels_out:
                max_nkpf = max_nkpf - max_nkpf % 2

        elif self._ker_factor in [8, 16]:
            if self._ker_factor * max_nkpf > self.Layer._channels_out:
                max_nkpf = self.Layer._channels_out/self._ker_factor
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
        elif self._ker_factor in [8]:
            depth_per_nkpf = 8
        else:
            AssertionError(
                "Invalid Ker factor of {}\n".format(self._ker_factor))

        # FIXME: delete this line after the design is calibracated
        self._pseudo_max_nkpf = max_nkpf
        
        if (max_nkpf % 2 and max_nkpf != 1):
            max_nkpf = max_nkpf - 1

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
            self._channel_in_tile_number == 1 and self._channels_out_tile_number == 1)

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
                max(total_density, 1)

            if remain_real_latency < consumed_real_latency:
                consumed_latency = remain_real_latency * max(total_density, 1)
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
        first_weight_load_latency = self._get_AXI_racing_latency_by_task(
            task_remain_latency_dict, task_data_density, 'weight', task_real_time_dict)
        accumulate_real_latency += first_weight_load_latency

        if first_row_step_flag:
            self._latency_dict['FirstWeightOverhead'] = accumulate_real_latency

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

        return accumulate_real_latency

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
                stage_latency_dict[stage_tag] = 0

            self._latency_dict['Istage{}Latency'.format(
                stage_tag)] = stage_latency_dict[stage_tag]

        self._latency_dict['IstageReadOverhead'] = self._latency_dict['ReadInputFirst_Total']
        self._latency_dict['IstageWriteOverhead'] = self._latency_dict['WriteOutputLast_Total']
        self._latency_dict['TotalLatency'] = self._latency_dict['IstageReadOverhead']\
            + self._latency_dict['IstageNoOutputLatency']\
            + self._latency_dict['IstageNormalInputLatency'] * (self._row_step_number - 3)\
            + self._latency_dict['IstageLastInputLatency']\
            + self._latency_dict['IstageNoInputLatency']\
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
        elif self._ker_factor in [8]:
            depth_per_nkpf = 8
        else:
            AssertionError(
                "Invalid Ker factor of {}\n".format(self._ker_factor))

        #FIXME: currently it is usind _pseudo_max_nkpf, shoud be using read max_nkpf
        kernel_load_count = self._compute_iter_length * self._pseudo_max_nkpf
        #self._channels_out_tile_size /     depth_per_nkpf

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
        self.get_channels_out_tile_size()

        self.get_ComputeKer16_latency()
        self.get_OStgBuffSeq_latency()
        self.get_ProcResult_latency()
        self.get_LoadKer_latency()

        self.get_ReadInput_latency()
        self.get_WriteOutput_latency()

        self.get_ProcIstg_latency()

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
        assert(w_h == w_w, "the window size is not square")
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
        assert(w_h == w_w, "the window size is not square")
        self._window_size = w_h
        self._layer_id = args_list[12]
        self._row_step = args_list[15]

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


if __name__ == "__main__":
    folder_name = sys.argv[1]
    layer_list = []
    csv_file = open("model_latency.csv", "w")
    for i in range(77):
        args_file_name = folder_name+"/args_conv_L"+str(i)

        if os.path.exists(args_file_name):
            conv_layer = ConvLayerInfo()
            conv_layer.set_from_file(args_file_name)
            test_IP = ConvIP(ConvIP, 32, 32, 8192, 2048, 4096)
            test_IP.load_layer(conv_layer)
            test_IP.get_ProcResult_latency()
            test_IP.get_LoadKer_latency()
            test_IP.get_ProcWeight_latency()
            test_IP.get_ReadInput_latency()
            test_IP.get_WriteOutput_latency()
            test_IP.get_ProcIstg_latency()

            print('items number', len(test_IP._latency_dict))
            pp = pprint.PrettyPrinter(indent=4)
            pp.pprint(test_IP._latency_dict)
            if(i == 0):
                test_IP.write_latency_title_tab(csv_file)
            test_IP.write_latency_data_tab(csv_file)
