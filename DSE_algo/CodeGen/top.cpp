void pipeSystem(
	ap<uint128> * D_M_out0,
	ap<uint128> * D_M_out1,
	ap<uint128> * M_ness_D0,
	ap<uint128> * M_ness_D1,
	ap<uint128> * M_ness_D2,
	ap<uint128> * M_ness_D3,
	ap<uint128> * M_ness_MUX10,
	ap<uint128> * C_M_out2,
	ap<uint128> * C_M_out3,
	ap<uint128> * M_ness_C0,
	ap<uint128> * M_ness_C1,
	ap<uint128> * M_ness_C2,
	ap<uint128> * M_ness_C3,
	ap<uint128> * B_M_out4,
	ap<uint128> * B_M_out5,
	ap<uint128> * M_ness_B0,
	ap<uint128> * M_ness_B1,
	ap<uint128> * M_ness_B2,
	ap<uint128> * M_ness_B3,
	ap<uint128> * M_ness_MUX00,
	ap<uint128> * A_M_in0,
	ap<uint128> * A_M_in1,
	ap<uint128> * M_ness_A0,
	ap<uint128> * M_ness_A1,
	ap<uint128> * M_ness_A2,
	ap<uint128> * M_ness_A3,
	ap<uint128> * M_ness_MUX20,
){
	#pragma HLS dataflow
	#pragma HLS INTERFACE ap_stable port=ap_clk_div2
		 static hls::stream< ap<uint128> > S15;
		 static hls::stream< ap<uint128> * > S6;
		 static hls::stream< ap<uint128> > S14;
		 static hls::stream< ap<uint128> * > S5;
		 static hls::stream< ap<uint128> * > S4;
		 static hls::stream< ap<uint128> * > S2;
		 static hls::stream< ap<uint128> * > S13;
		 static hls::stream< ap<uint128> > S0;
		 static hls::stream< ap<uint128> > S9;
		 static hls::stream< ap<uint128> * > S12;
		 static hls::stream< ap<uint128> > S8;
		 static hls::stream< ap<uint128> * > S1;
		 static hls::stream< ap<uint128> * > S0;
		 static hls::stream< ap<uint128> > S11;
		 static hls::stream< ap<uint128> > S10;
		 static hls::stream< ap<uint128> > S1;
		 static hls::stream< ap<uint128> * > S3;
		 static hls::stream< ap<uint128> * > S7;
		D::Convolution(
			D_M_out0,
			D_M_out1,
			S10,
			S11,
			S10,
			S11,
			M_ness_D0,
			M_ness_D1,
			M_ness_D2,
			M_ness_D3,
		);
		MUX1to2(
			S12,
			S13,
			S12,
			S13,
			M_ness_MUX10,
		);
		C::Convolution(
			C_M_out2,
			C_M_out3,
			S8,
			S9,
			S8,
			S9,
			M_ness_C0,
			M_ness_C1,
			M_ness_C2,
			M_ness_C3,
		);
		B::Convolution(
			B_M_out4,
			B_M_out5,
			S14,
			S15,
			S14,
			S15,
			M_ness_B0,
			M_ness_B1,
			M_ness_B2,
			M_ness_B3,
		);
		MUX2to1(
			S4,
			S5,
			S6,
			S7,
			S4,
			S5,
			S6,
			S7,
			M_ness_MUX00,
		);
		A::Convolution(
			A_M_in0,
			A_M_in1,
			S0,
			S1,
			M_ness_A0,
			M_ness_A1,
			M_ness_A2,
			M_ness_A3,
		);
		MUX2to1(
			S0,
			S1,
			S2,
			S3,
			S0,
			S1,
			S2,
			S3,
			M_ness_MUX20,
		);
}