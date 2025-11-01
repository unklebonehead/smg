#!/usr/bin/env python3
import sys
import os
import subprocess
import threading
from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    Slot,
    Signal,
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QFileDialog,
    QProgressBar,
    QMessageBox,
)

# --- Path Configuration ---
def get_cli_path():
    """
    Get the path to the 'mg_cli.py' script, whether we are
    running as a normal .py script or as a "frozen" PyInstaller exe.
    """
    if getattr(sys, 'frozen', False):
        # We are running in a bundle (as an exe)
        # sys._MEIPASS is a special PyInstaller variable for the temp dir
        base_path = sys._MEIPASS
    else:
        # We are running as a normal script
        # Get the directory of the current script
        base_path = os.path.dirname(os.path.abspath(__file__))

    # Assuming 'matchering-cli/mg_cli.py' is relative to this script
    # or inside the frozen app's root
    cli_path = os.path.join(base_path, "matchering-cli", "mg_cli.py")

    # Fallback to home directory if not found (original behavior)
    if not os.path.exists(cli_path) and not getattr(sys, 'frozen', False):
         base_path = os.path.expanduser("~")
         cli_path = os.path.join(base_path, "matchering-cli", "mg_cli.py")

    return cli_path

# Get the path to the CLI script
CLI_SCRIPT_PATH = get_cli_path()

# --- Worker Thread Setup ---
# This is necessary to run the 'subprocess' without
# freezing the entire GUI.

class WorkerSignals(QObject):
    """
    Holds the signals that the worker thread can emit.
    """

    finished = Signal()
    error = Signal(str)
    status = Signal(str)
    progress = Signal(int)


class SingleMasterWorker(QRunnable):
    """
    Worker thread for mastering a single file.
    """

    def __init__(self, command):
        super().__init__()
        self.command = command
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            self.signals.status.emit("Processing... (this can take a while)")
            print(f"Running command: {' '.join(self.command)}") # Log command
            result = subprocess.run(
                self.command, capture_output=True, text=True, check=True, encoding='utf-8'
            )
            print("STDOUT:", result.stdout)
            self.signals.status.emit("Success! File mastered.")

        except subprocess.CalledProcessError as e:
            print("STDERR:", e.stderr)
            self.signals.error.emit(f"An error occurred:\n\n{e.stderr}")
            self.signals.status.emit("Error! Check terminal for details.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            self.signals.error.emit(f"An unexpected error occurred:\n\n{str(e)}")
            self.signals.status.emit("Error! Check terminal for details.")
        finally:
            self.signals.finished.emit()


class BatchMasterWorker(QRunnable):
    """
    Worker thread for mastering a batch of files.
    Now accepts either a directory OR a list of files.
    """

    def __init__(self, ref_file, input_dir, input_files, output_dir, bit_depth):
        super().__init__()
        self.ref_file = ref_file
        self.input_dir = input_dir
        self.input_files = input_files # NEW: Will be a list of paths
        self.output_dir = output_dir
        self.bit_depth = bit_depth
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            files_to_process = []
            if self.input_files:
                # We were given a specific list of files
                print(f"Processing {len(self.input_files)} selected files.")
                files_to_process = self.input_files
            elif self.input_dir:
                # We were given a directory, so scan it
                print(f"Scanning directory: {self.input_dir}")
                found_files = [
                    os.path.join(self.input_dir, f) # Get full path
                    for f in os.listdir(self.input_dir)
                    if f.lower().endswith((".wav", ".flac", ".aiff", ".mp3"))
                ]
                if not found_files:
                    self.signals.error.emit("No audio files found in the input folder.")
                    self.signals.finished.emit()
                    return
                files_to_process = found_files
            else:
                # This shouldn't happen if GUI logic is correct
                self.signals.error.emit("No input source provided.")
                self.signals.finished.emit()
                return

            total_files = len(files_to_process)
            print(f"Found {total_files} files to process.")

            for i, full_filepath in enumerate(files_to_process):
                filename = os.path.basename(full_filepath)
                base, _ = os.path.splitext(filename)

                input_file = full_filepath # Use the full path directly

                output_file = os.path.join(
                    self.output_dir, f"{base} (Mastered).flac"
                )

                self.signals.status.emit(
                    f"Processing {i+1}/{total_files}: {filename}"
                )
                self.signals.progress.emit(int(((i + 1) / total_files) * 100))

                command = [
                    "python3",
                    CLI_SCRIPT_PATH,
                    "-b",
                    self.bit_depth,
                    input_file,
                    self.ref_file,
                    output_file,
                ]

                print(f"Running command: {' '.join(command)}") # Log command
                subprocess.run(
                    command, capture_output=True, text=True, check=True, encoding='utf-8'
                )

            self.signals.status.emit(
                f"Batch complete! {total_files} files mastered."
            )

        except subprocess.CalledProcessError as e:
            # Handle errors from the CLI script
            print("STDERR:", e.stderr)
            error_msg = f"Failed on file: {filename}\n\n{e.stderr}"
            self.signals.error.emit(error_msg)
            self.signals.status.emit("Error! Check terminal for details.")
        except Exception as e:
            # Handle other errors (file not found, etc.)
            print(f"An unexpected error occurred: {e}")
            self.signals.error.emit(f"An error occurred:\n\n{str(e)}")
            self.signals.status.emit("Error! Check terminal for details.")
        finally:
            self.signals.finished.emit()


# --- Main Application Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Mastering GUI (Qt Edition)")
        self.setMinimumSize(600, 350)

        # NEW: To store paths from "Select Files"
        self.batch_selected_files = []

        # We need a thread pool to run our worker tasks
        self.threadpool = QThreadPool()
        print(f"Max threads: {self.threadpool.maxThreadCount()}")

        # Main widget and tab setup
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.single_tab = QWidget()
        self.batch_tab = QWidget()

        self.tabs.addTab(self.single_tab, "Single Song")
        self.tabs.addTab(self.batch_tab, "Batch Master")

        # Create the layout for each tab
        self.create_single_tab_layout()
        self.create_batch_tab_layout()

    def create_single_tab_layout(self):
        layout = QVBoxLayout(self.single_tab)

        # Reference File
        ref_layout = QHBoxLayout()
        self.sf_ref_label = QLineEdit()
        self.sf_ref_label.setReadOnly(True)
        self.sf_ref_label.setPlaceholderText("Path to your reference track...")
        ref_layout.addWidget(QLabel("Reference:"))
        ref_layout.addWidget(self.sf_ref_label)
        sf_ref_btn = QPushButton("Browse...")
        sf_ref_btn.clicked.connect(self.select_sf_ref)
        ref_layout.addWidget(sf_ref_btn)
        layout.addLayout(ref_layout)

        # Target File
        target_layout = QHBoxLayout()
        self.sf_target_label = QLineEdit()
        self.sf_target_label.setReadOnly(True)
        self.sf_target_label.setPlaceholderText("Path to the song you want to master...")
        target_layout.addWidget(QLabel("Target:"))
        target_layout.addWidget(self.sf_target_label)
        sf_target_btn = QPushButton("Browse...")
        sf_target_btn.clicked.connect(self.select_sf_target)
        target_layout.addWidget(sf_target_btn)
        layout.addLayout(target_layout)

        # Output File
        output_layout = QHBoxLayout()
        self.sf_output_entry = QLineEdit()
        self.sf_output_entry.setPlaceholderText("Where to save the mastered file...")
        output_layout.addWidget(QLabel("Output:"))
        output_layout.addWidget(self.sf_output_entry)
        sf_output_btn = QPushButton("Save As...")
        sf_output_btn.clicked.connect(self.select_sf_output)
        output_layout.addWidget(sf_output_btn)
        layout.addLayout(output_layout)

        # Bit Depth
        bit_layout = QHBoxLayout()
        self.sf_bit_entry = QLineEdit("24")
        self.sf_bit_entry.setFixedWidth(50)
        bit_layout.addWidget(QLabel("Bit-depth (16, 24, 32):"))
        bit_layout.addWidget(self.sf_bit_entry)
        bit_layout.addStretch()  # Pushes items to the left
        layout.addLayout(bit_layout)

        layout.addStretch()  # Spacer

        # Run Button
        self.sf_run_button = QPushButton("MASTER SINGLE SONG")
        self.sf_run_button.setMinimumHeight(40)
        self.sf_run_button.clicked.connect(self.run_single_master)
        layout.addWidget(self.sf_run_button)

        # Status Label
        self.sf_status_label = QLabel("Status: Idle")
        self.sf_status_label.setAlignment(Qt.AlignCenter)
        self.sf_status_label.setStyleSheet(
            "border: 1px solid gray; padding: 5px; background-color: #f0f0f0;"
        )
        layout.addWidget(self.sf_status_label)

    def create_batch_tab_layout(self):
        layout = QVBoxLayout(self.batch_tab)

        # Reference File
        ref_layout = QHBoxLayout()
        self.b_ref_label = QLineEdit()
        self.b_ref_label.setReadOnly(True)
        self.b_ref_label.setPlaceholderText("Path to your reference track...")
        ref_layout.addWidget(QLabel("Reference:"))
        ref_layout.addWidget(self.b_ref_label)
        b_ref_btn = QPushButton("Browse...")
        b_ref_btn.clicked.connect(self.select_b_ref)
        ref_layout.addWidget(b_ref_btn)
        layout.addLayout(ref_layout)

        # --- MODIFIED Input Section ---
        input_layout = QHBoxLayout()
        self.b_input_display = QLineEdit() # Renamed from b_input_label
        self.b_input_display.setReadOnly(True)
        self.b_input_display.setPlaceholderText("Select an input directory OR multiple files...")
        input_layout.addWidget(QLabel("Input:")) # Renamed from "Input Dir:"
        input_layout.addWidget(self.b_input_display)

        # Button for selecting directory
        b_input_dir_btn = QPushButton("Select Directory...") # Renamed
        b_input_dir_btn.clicked.connect(self.select_b_input_dir) # Renamed
        input_layout.addWidget(b_input_dir_btn)

        # NEW Button for selecting files
        b_input_files_btn = QPushButton("Select Files...")
        b_input_files_btn.clicked.connect(self.select_b_input_files)
        input_layout.addWidget(b_input_files_btn)

        layout.addLayout(input_layout)
        # --- End MODIFIED Input Section ---

        # Output Folder
        output_layout = QHBoxLayout()
        self.b_output_label = QLineEdit()
        self.b_output_label.setReadOnly(True)
        self.b_output_label.setPlaceholderText("Select a folder to save mastered files...")
        output_layout.addWidget(QLabel("Output Dir:"))
        output_layout.addWidget(self.b_output_label)
        b_output_btn = QPushButton("Browse...")
        b_output_btn.clicked.connect(self.select_b_output)
        output_layout.addWidget(b_output_btn)
        layout.addLayout(output_layout)

        # Bit Depth
        bit_layout = QHBoxLayout()
        self.b_bit_entry = QLineEdit("24")
        self.b_bit_entry.setFixedWidth(50)
        bit_layout.addWidget(QLabel("Bit-depth (16, 24, 32):"))
        bit_layout.addWidget(self.b_bit_entry)
        bit_layout.addStretch()
        layout.addLayout(bit_layout)

        layout.addStretch()

        # Run Button
        self.b_run_button = QPushButton("MASTER BATCH")
        self.b_run_button.setMinimumHeight(40)
        self.b_run_button.clicked.connect(self.run_batch_master)
        layout.addWidget(self.b_run_button)

        # Progress Bar
        self.b_progress = QProgressBar()
        self.b_progress.setVisible(False)
        self.b_progress.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.b_progress)

        # Status Label
        self.b_status_label = QLabel("Status: Idle")
        self.b_status_label.setAlignment(Qt.AlignCenter)
        self.b_status_label.setStyleSheet(
            "border: 1px solid gray; padding: 5px; background-color: #f0f0f0;"
        )
        layout.addWidget(self.b_status_label)

    # --- Single Tab Functions ---
    def select_sf_ref(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Reference File", filter="Audio Files (*.wav *.flac *.aiff *.mp3)")
        if path:
            self.sf_ref_label.setText(path)

    def select_sf_target(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Target Song", filter="Audio Files (*.wav *.flac *.aiff *.mp3)")
        if path:
            self.sf_target_label.setText(path)
            # Suggest output name
            base = os.path.basename(path)
            name, _ = os.path.splitext(base)
            dir_ = os.path.dirname(path)
            suggested_output = os.path.join(dir_, f"{name} (Mastered).flac")
            self.sf_output_entry.setText(suggested_output)

    def select_sf_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Mastered File As...", filter="FLAC File (*.flac)")
        if path:
            # Ensure it has the .flac extension
            if not path.lower().endswith(".flac"):
                path += ".flac"
            self.sf_output_entry.setText(path)

    def run_single_master(self):
        ref_file = self.sf_ref_label.text()
        target_file = self.sf_target_label.text()
        output_file = self.sf_output_entry.text()
        bit_depth = self.sf_bit_entry.text()

        if not all([ref_file, target_file, output_file, bit_depth]):
            QMessageBox.warning(self, "Missing Info", "Please fill in all fields.")
            return

        if not bit_depth in ("16", "24", "32"):
            QMessageBox.warning(self, "Invalid Bit-depth", "Please enter 16, 24, or 32 for bit-depth.")
            return

        command = [
            "python3",
            CLI_SCRIPT_PATH,
            "-b",
            bit_depth,
            target_file,
            ref_file,
            output_file,
        ]

        self.sf_run_button.setDisabled(True)
        self.sf_status_label.setStyleSheet("border: 1px solid gray; padding: 5px; background-color: #e0e0ff;") # In progress color
        worker = SingleMasterWorker(command)
        worker.signals.status.connect(self.sf_status_label.setText)
        worker.signals.error.connect(self.on_single_error)
        worker.signals.finished.connect(self.on_single_finished)

        self.threadpool.start(worker)

    def on_single_finished(self):
        self.sf_run_button.setDisabled(False)
        if "Success" in self.sf_status_label.text():
             self.sf_status_label.setStyleSheet("border: 1px solid gray; padding: 5px; background-color: #e0ffe0;") # Success color

    def on_single_error(self, err_msg):
        self.sf_status_label.setStyleSheet("border: 1px solid gray; padding: 5px; background-color: #ffe0e0;") # Error color
        QMessageBox.critical(self, "Error", err_msg)


    # --- Batch Tab Functions ---
    def select_b_ref(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Reference File", filter="Audio Files (*.wav *.flac *.aiff *.mp3)")
        if path:
            self.b_ref_label.setText(path)

    def select_b_input_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if path:
            self.b_input_display.setText(path)
            self.batch_selected_files = [] # Clear file list
            # Suggest output dir
            self.b_output_label.setText(os.path.join(path, "Mastered"))

    # NEW Function
    def select_b_input_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Input Files", filter="Audio Files (*.wav *.flac *.aiff *.mp3)")
        if paths:
            self.batch_selected_files = paths
            self.b_input_display.setText(f"{len(paths)} files selected")
            # Suggest output dir based on the first file's parent dir
            if paths:
                parent_dir = os.path.dirname(paths[0])
                self.b_output_label.setText(os.path.join(parent_dir, "Mastered"))

    def select_b_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.b_output_label.setText(path)

    def run_batch_master(self):
        ref_file = self.b_ref_label.text()
        input_display_text = self.b_input_display.text()
        input_files_list = self.batch_selected_files
        output_dir = self.b_output_label.text()
        bit_depth = self.b_bit_entry.text()

        input_dir = ""
        input_files = []

        # Determine input source
        if input_files_list:
            print("Using selected files list.")
            input_files = input_files_list
        elif os.path.isdir(input_display_text):
            print("Using selected directory path.")
            input_dir = input_display_text
        else:
            QMessageBox.warning(self, "Missing Info", "Please select an input directory OR input files.")
            return

        if not all([ref_file, output_dir, bit_depth]):
            QMessageBox.warning(self, "Missing Info", "Please fill in all fields (Reference, Output Dir, Bit-depth).")
            return

        if not bit_depth in ("16", "24", "32"):
            QMessageBox.warning(self, "Invalid Bit-depth", "Please enter 16, 24, or 32 for bit-depth.")
            return

        # Ensure output directory exists
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                print(f"Created output directory: {output_dir}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create output directory:\n{e}")
                return

        self.b_run_button.setDisabled(True)
        self.b_progress.setVisible(True)
        self.b_progress.setValue(0)
        self.b_status_label.setStyleSheet("border: 1px solid gray; padding: 5px; background-color: #e0e0ff;") # In progress color

        worker = BatchMasterWorker(
            ref_file=ref_file,
            input_dir=input_dir,
            input_files=input_files,
            output_dir=output_dir,
            bit_depth=bit_depth
        )
        worker.signals.status.connect(self.b_status_label.setText)
        worker.signals.progress.connect(self.b_progress.setValue)
        worker.signals.error.connect(self.on_batch_error)
        worker.signals.finished.connect(self.on_batch_finished)

        self.threadpool.start(worker)

    def on_batch_finished(self):
        self.b_run_button.setDisabled(False)
        self.b_progress.setVisible(False)
        if "complete" in self.b_status_label.text():
            self.b_status_label.setStyleSheet("border: 1px solid gray; padding: 5px; background-color: #e0ffe0;") # Success color

    def on_batch_error(self, err_msg):
        self.b_status_label.setStyleSheet("border: 1px solid gray; padding: 5px; background-color: #ffe0e0;") # Error color
        self.b_progress.setVisible(False)
        QMessageBox.critical(self, "Batch Error", err_msg)


# --- Entry Point ---
if __name__ == "__main__":
    print(f"Checking for CLI script at: {CLI_SCRIPT_PATH}")
    if not os.path.exists(CLI_SCRIPT_PATH):
        # We need to create an app to show the popup,
        # even for an error
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Fatal Error",
            f"Could not find the Matchering CLI script at:\n{CLI_SCRIPT_PATH}\n\nPlease make sure the 'matchering-cli' folder is in the same directory as this application.",
        )
        sys.exit(1)

    print("CLI script found. Starting application...")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
