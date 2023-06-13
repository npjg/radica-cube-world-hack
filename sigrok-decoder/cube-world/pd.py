import sigrokdecode as srd

class SamplerateError(Exception):
    pass

PULSE_WIDTH_TOLERANCE_MICROSECONDS = 10

ATTENTION_LOW_PULSE_WIDTH_MICROSECONDS = 234
ATTENTION_HIGH_PULSE_WIDTH_MICROSECONDS = 53

BINARY_0_PULSE_WIDTH_MICROSECONDS = 95
BINARY_1_PULSE_WIDTH_MICROSECONDS = 175

class Decoder(srd.Decoder):
    api_version = 3
    id = 'cubeworld'
    name = 'Cube World'
    longname = 'Radica Cube World Protocol'
    desc = 'Asynchronous, serial bus'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['cubeworld']
    channels = ({'id': 'd0', 'name': 'Data', 'desc': 'Cube data line'}, )
    options = ()
    tags = ['Embedded/industrial']

    annotations = (                        # Implicitly assigned annotation type ID
        ('bit', 'Bit'),                    # 0
        ('preamble', 'Preamble'),          # 1
        ('postamble', 'Postamble'),        # 2
        ('warnings', 'Warnings'),          # 3
        ('nibble', 'Nibble'),              # 4
        # This is temporary until I can figure out what the components of the message mean.
        # This is so I can easily compare entire messages against each other.
        ('transmission', 'Entire Transmission'), # 5
    )

    annotation_rows = (
        ('bits', 'Bits', (0, 1, 2)),
        ('nibbles', 'Nibbles', (4,)),
        ('transmissions', 'Transmissions', (5,)),
        ('warnings', 'Warnings', (3,)),
    )

    def __init__(self):
        self.reset()
        self.starting_sample = None
        self.ending_sample = None
        self.nibble_start_sample = None
        self.nibble_end_sample = None
        self.bits_read = 0
        self.bits_in_nibble = ''
        self.nibbles_in_transmission = ''

    def reset(self):
        self.samplerate = None

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value / 1000000

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def get_high_pulse_length(self, save_start = False):
        # READ THE RISING EDGE.
        logic_value = self.wait({0: 'h'})
        rising_edge_sample_index = self.samplenum
        if save_start:
            self.starting_sample = rising_edge_sample_index

        # READ THE FALLING EDGE.
        logic_value = self.wait({0: 'l'})
        falling_edge_sample_index = self.samplenum

        # CALCULATE THE PULSE LENGTH.
        pulse_total_samples = falling_edge_sample_index - rising_edge_sample_index
        pulse_length = pulse_total_samples / self.samplerate
        return pulse_length

    def get_low_pulse_length(self, save_start = False):
        # READ THE FALLING EDGE.
        logic_value = self.wait({0: 'l'})
        falling_edge_sample_index = self.samplenum
        if save_start:
            self.starting_sample = falling_edge_sample_index

        # READ THE RISING EDGE.
        logic_value = self.wait({0: 'h'})
        rising_edge_sample_index = self.samplenum

        # CALCULATE THE PULSE LENGTH.
        pulse_total_samples = rising_edge_sample_index - falling_edge_sample_index
        pulse_length = pulse_total_samples / self.samplerate
        return pulse_length

    ## \return True if the preamble is read successfully; False otherwise.
    def read_preamble(self) -> bool:
        low_pulse_length = self.get_low_pulse_length(save_start = True)
        low_pulse_length_in_range = low_pulse_length > 200 and low_pulse_length < 300
        if low_pulse_length_in_range:
            high_pulse_length = self.get_high_pulse_length()
            high_pulse_length_in_range = high_pulse_length >= 48 and high_pulse_length <= 70
            if high_pulse_length_in_range:
                # MARK THE PREAMBLE.
                return True
            else:
                # MARK AN INVALID PREAMBLE.
                # self.put(starting_sample, ending_sample, self.out_ann, [3, ['Bad Preamble', 'Bad P', 'BP']])
                pass

        return False

    def read_bit(self):
        starting_sample = self.samplenum
        high_pulse_length = self.get_high_pulse_length(save_start = True)
        MAX_HIGH_PULSE_LENGTH_IN_MICROSECONDS = 80
        if high_pulse_length <= MAX_HIGH_PULSE_LENGTH_IN_MICROSECONDS:
            # INDICATE THERE ARE NO MORE BITS TO READ.
            return False

        if self.bits_read == 0:
            self.nibble_start_sample = starting_sample

        low_pulse_length = self.get_low_pulse_length()
        ending_sample = self.samplenum
        MAX_ZERO_BIT_LOW_LENGTH_IN_MICROSECONDS = 115
        MIN_ONE_BIT_LOW_LENGTH_IN_MICROSECONDS = 150
        if low_pulse_length  <= MAX_ZERO_BIT_LOW_LENGTH_IN_MICROSECONDS:
            # MARK A 0 BIT.
            self.put(starting_sample, ending_sample, self.out_ann, [0, ['0']])
            self.bits_in_nibble += '0'
            self.bits_read += 1
        elif low_pulse_length >= MIN_ONE_BIT_LOW_LENGTH_IN_MICROSECONDS:
            # MARK A 1 BIT.
            self.put(starting_sample, ending_sample, self.out_ann, [0, ['1']])
            self.bits_in_nibble += '1'
            self.bits_read += 1
        else:
            # MARK AN INVALID BIT LENGTH.
            self.put(starting_sample, ending_sample, self.out_ann, [3, ['Bad Bit Length', 'Bad Bit', 'B']])

        if self.bits_read % 4 == 0:
            self.nibble_end_sample = ending_sample
            hex_digit = hex(int(self.bits_in_nibble, 2))
            self.put(self.nibble_start_sample, self.nibble_end_sample, self.out_ann, [4, [hex_digit]])
            print(hex_digit, end = ' ')
            self.bits_in_nibble = ''
            self.nibbles_in_transmission += hex_digit + ' '
            self.nibble_start_sample = self.nibble_end_sample

        # INDICATE THERE ARE MORE BITS TO READ.
        return True

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Samplerate is required to calculate pulse lengths. Cannot decode without samplerate.')
        
        while True:
            if self.read_preamble():
                print("***")
                self.bits_read = 0
                self.bits_in_nibble = ''

                self.get_low_pulse_length()
                self.ending_sample = self.samplenum
                self.put(self.starting_sample, self.ending_sample, self.out_ann, [1, ['Preamble', 'Pre', 'P']])

                transmission_start_sample = self.samplenum
                more_bits_to_read = self.read_bit()
                while more_bits_to_read:
                    more_bits_to_read = self.read_bit()
                transmission_end_sample = self.samplenum

                self.get_low_pulse_length()
                self.ending_sample = self.samplenum
                self.put(self.starting_sample, self.ending_sample, self.out_ann, [1, ['Postamble', 'Post', 'P']])
                print()

                self.put(transmission_start_sample, transmission_end_sample, self.out_ann, [5, [self.nibbles_in_transmission]])
                self.nibbles_in_transmission = ''
