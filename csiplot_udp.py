import socket
import struct
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading
from collections import deque

# --- Global Data Structures ---
# Use a lock for thread-safe access to shared data
data_lock = threading.Lock()

# latest_csi_data stores the most recent CSI for each RX port
latest_csi_data = {}
# ta_history stores a continuous record of received Time Alignment values
ta_history = deque() # Use deque for efficient appends

# --- Matplotlib Global Variables ---
fig = None
axs = {} # Use a dictionary for flexible axis management
lines = {}
rx_ports = set()


def recv_csi_udp(listen_ip="0.0.0.0", listen_port=5000):
    """
    This function runs in a background thread to receive SCTP data,
    parse it, and update the global data structures.
    """
    global latest_csi_data, rx_ports, ta_history
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((listen_ip, listen_port))

    print(f"Listening(UDP) on {listen_ip}:{listen_port} ...")

    while True:
        # It's better to handle potential partial receives in a real application
        data, addr = sock.recvfrom(8192)

        floats = np.frombuffer(data, dtype = np.float32)
 
        if not data:
            break

        # Convert raw bytes to a numpy array of floats
        floats = np.frombuffer(data, dtype=np.float32)

        # --- MODIFIED PARSING LOGIC ---
        # New format: [rx_port, tx_port, time_alignment, csi_data...]
        if len(floats) < 3:
            continue

        rx_port = int(floats[0])
        tx_port = int(floats[1])
        time_alignment_s = floats[2] # Extract Time Alignment in seconds

        # The rest of the data is the complex CSI
        csi_complex = floats[3:].reshape(-1, 2)
        csi = csi_complex[:, 0] + 1j * csi_complex[:, 1]
        
        # Use a lock to safely update shared data
        with data_lock:
            latest_csi_data[rx_port] = csi
            ta_history.append(time_alignment_s * 1e6) # Convert to microseconds and store
            rx_ports.add(rx_port)

        print(f"RX={rx_port}, TX={tx_port}, TA={time_alignment_s * 1e6:.3f} µs, CSI_len={len(csi)}")

    conn.close()
    sock.close()


def setup_plots():
    """
    Sets up the matplotlib figure and axes before the animation starts.
    The layout is adjusted to include a dedicated plot for Time Alignment.
    """
    global fig, axs, lines
    
    # Wait until we have received at least one packet to know the number of RX ports
    while not rx_ports:
        #print("Waiting for first data packet to setup plots...")
        threading.Event().wait(0.5)
    
    n_rx = len(rx_ports)
    rx_port_list = sorted(list(rx_ports))
    
    print(f"Setting up plots for RX ports: {rx_port_list}")
    
    # --- MODIFIED PLOT LAYOUT ---
    # Create a figure with n_rx columns for CSI and one extra column for TA
    fig = plt.figure(figsize=(4 * (n_rx + 1), 8))
    # Use GridSpec for more flexible layout
    gs = fig.add_gridspec(2, n_rx + 1)

    for i, rx_port in enumerate(rx_port_list):
        # CSI Magnitude Plot
        ax_mag = fig.add_subplot(gs[0, i])
        l1, = ax_mag.plot([], [], label=f'RX {rx_port}')
        ax_mag.set_title(f"RX {rx_port} - Magnitude", fontsize=14)
        ax_mag.set_ylabel('Magnitude', fontsize=12)
        ax_mag.set_xlabel('Subcarrier Index', fontsize=12)
        ax_mag.grid(True)
        ax_mag.set_ylim(0, 1)

        # CSI Phase Plot
        ax_phase = fig.add_subplot(gs[1, i])
        l2, = ax_phase.plot([], [], label=f'RX {rx_port}')
        ax_phase.set_title(f"RX {rx_port} - Phase", fontsize=14)
        ax_phase.set_ylabel('Unwrapped Phase (rad)', fontsize=12)
        ax_phase.set_xlabel('Subcarrier Index', fontsize=12)
        ax_phase.grid(True)
        ax_phase.set_ylim(-10, 10)

        # Store axes and lines
        axs[rx_port] = {'mag': ax_mag, 'phase': ax_phase}
        lines[rx_port] = {'mag': l1, 'phase': l2}

    # --- NEW: Setup the Time Alignment Plot ---
    # This plot will span both rows in the last column
    ax_ta = fig.add_subplot(gs[:, n_rx])
    l_ta, = ax_ta.plot([], [], 'r.-', label='Time Alignment') # Red line with dots
    ax_ta.set_title("Time Alignment History", fontsize=14)
    ax_ta.set_ylabel("Time Alignment (µs)", fontsize=12)
    ax_ta.set_xlabel("Sample Index", fontsize=12)
    ax_ta.grid(True)
    ax_ta.legend()
    
    # Store the TA axis and line
    axs['ta'] = ax_ta
    lines['ta'] = l_ta

    plt.tight_layout(pad=2.0)


def update_plots(frame):
    """
    This function is called repeatedly by FuncAnimation to update plot data.
    """
    global latest_csi_data, ta_history, lines, axs
    
    updated_lines = []

    # Use a lock to safely read the shared data
    with data_lock:
        local_csi_data = latest_csi_data.copy()
        local_ta_history = list(ta_history)

    if not local_csi_data or not lines:
        return []

    # --- Update CSI Plots ---
    for rx_port, csi_data in local_csi_data.items():
        if rx_port not in lines:
            continue
            
        mag = np.abs(csi_data)
        phase_unwrapped = np.unwrap(np.angle(csi_data))
        
        x_data = np.arange(len(mag))
        
        # Update magnitude data and limits
        lines[rx_port]['mag'].set_data(x_data, mag)
        axs[rx_port]['mag'].set_xlim(0, len(mag) - 1 if len(mag) > 1 else 1)
        
        # Update phase data and limits
        lines[rx_port]['phase'].set_data(x_data, phase_unwrapped)
        axs[rx_port]['phase'].set_xlim(0, len(phase_unwrapped) - 1 if len(phase_unwrapped) > 1 else 1)
        
        updated_lines.extend([lines[rx_port]['mag'], lines[rx_port]['phase']])
    
    # --- NEW: Update Time Alignment Plot ---
    if 'ta' in lines and local_ta_history:
        ta_line = lines['ta']
        ta_ax = axs['ta']
        
        # Create x-axis as sample indices
        x_ta_data = np.arange(len(local_ta_history))
        
        # Set new data
        ta_line.set_data(x_ta_data, local_ta_history)
        
        # Auto-scale the axes for the TA plot
        ta_ax.relim()
        ta_ax.autoscale_view(True, True, True)
        
        updated_lines.append(ta_line)

    return updated_lines


if __name__ == "__main__":
    # Start the SCTP receiver in a separate, daemonic thread
    t = threading.Thread(target=recv_csi_udp, args=("0.0.0.0", 5000), daemon=True)
    t.start()
    
    # Setup the plots in the main thread
    setup_plots()
    
    # Start the animation
    ani = FuncAnimation(fig, update_plots, interval=50, blit=False)
    plt.show()
