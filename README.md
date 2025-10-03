# udp_5g_csi_plot
This repository is about how to transfer CSI (Channel State Information) and TA (Timing Advance) offset from a SRSRAN physical layer implementation to a host, and for real-time plotting of the received data. And the protocol is UDP.
## Files
- srs_estimator_generic_impl.cpp
  Handling physical layer to send CSI and TA offset to another host, using UDP protocol by minor change, please see the comment on line 119-120 for details.
- csiplot_udp.py
  Receiver script thst collects transmitted CSI and TA offset in real time.
## Usage
1. Set up destination address to match the receiver host in SRSRAN side.
2. Run the receiver.
   ```bash
   python3 csiplot_udp.py
