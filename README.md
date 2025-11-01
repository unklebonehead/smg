## Simple Mastering GUI
<img width="730" height="508" alt="Screenshot_20251101_122510" src="https://github.com/user-attachments/assets/d2c1c633-df26-4d58-87f4-75fd483ed063" />

A simple, open-source Qt6 (PySide6) graphical user interface for the powerful matchering-cli audio mastering tool.

This app provides a user-friendly frontend for mastering single songs or entire batches of audio files without having to remember command-line arguments.

### Features
Two Modes:
- Single Song: Master one track at a time.
- Batch Master: Master an entire folder of audio files to a new output directory.

Native GUI: Built with PySide6 (Qt) for a native look and feel, especially on Qt-based desktops like Plasma and Hyprland.

Dependencies
This GUI is a frontend. The heavy lifting is done by [sergree's](https://github.com/sergree) [matchering-cli](https://github.com/sergree/matchering-cli) and ffmpeg. You must install all of these dependencies for the app to work.
1. System-Level Dependencies
You need git, ffmpeg, and libsndfile.

On a OpenMandriva-based system:
```sudo dnf install git ffmpeg libsndfile1```

2. Python Dependencies
You need python3 and the following pip packages:
- PySide6 (for the GUI)
- matchering (for the core logic)
- numpy, scipy, soundfile, statsmodels, resampy (as dependencies of matchering)

You can install them all with pip:
```python3 -m pip install PySide6 matchering```

3. The Matchering CLI Script
This GUI requires the matchering-cli script repository.
You must clone this repository to your home directory.

```cd ~```
```git clone [https://github.com/sergree/matchering-cli.git](https://github.com/sergree/matchering-cli.git)```


The app is hard-coded to look for the script at $HOME/matchering-cli/mg_cli.py.

How to Run
- Download the GUI Script:
- Save the mastering_ui.py script to your computer.
- Make it Executable:
```chmod +x mastering_ui.py```
- Run it:
```./mastering_ui.py```


### How to Use
#### Single Song Tab
- Reference: Click "Browse..." to select your reference track (the song you want to sound like).
- Target: Click "Browse..." to select your target song (the one you want to master).
- Output: An output file (e.g., YourSong (Mastered).flac) will be suggested. You can change this by typing or clicking "Save As...".
- Bit-depth: Set to 24 by default. You can change this to 16 or 32.
- Click MASTER SINGLE SONG. The app will process the file and update the status bar when finished.
#### Batch Master Tab
- Reference: Click "Browse..." to select your reference track.
- Input Dir: Click "Browse..." to select the folder containing all the .wav (or other) files you want to master.
- Output Dir: An output folder (e.g., .../Input-Dir/Mastered) will be suggested. The app will create this folder if it doesn't exist.
- Bit-depth: Set to 24 by default.
- Click MASTER BATCH. A progress bar will appear as the app masters every audio file in the input directory.

#### How to Build a Standalone Executable (Optional)
There is an executable in this repo but if you prefer you can build your own.

You can package this GUI, all its Python dependencies, and the matchering-cli script into a single executable file using PyInstaller.

Note: This will not bundle the system dependencies (ffmpeg, libsndfile1). Users will still need to install those.

- Install PyInstaller:
```python3 -m pip install pyinstaller```
- Run the Build Command:
- Run this from the same directory as mastering_ui.py:
```pyinstaller --onefile --windowed --add-data="$HOME/matchering-cli:matchering-cli" --name="Simple Mastering GUI" mastering_ui.py```

#### Find Your App:
Your new standalone executable, named Simple Mastering GUI, will be in the dist/ folder.
### License
matchering and matchering-cli is licensed under the GPLv3. To respect that license and the work that sergree has done, this GUI is also released under the GPLv3. Please send any donations to him.
