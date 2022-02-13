import xml.etree.ElementTree as ET
import sys
import shutil
import urllib
import subprocess
import argparse
import wave
import aifc
from pathlib import PureWindowsPath, Path


def print_structure(xml_root):
    playlist_arr = []
    for elem in xml_root.iter("NODE"):
        for playlist in elem.iterfind('NODE[@Type="1"]'):
            playlist_arr.append(playlist.attrib["Name"])
    playlist_count = len(playlist_arr)
    print(str(playlist_count) + " playlists found:")
    for counter, item in enumerate(playlist_arr):
        print(str(counter) + " - " + item)
    print("E - Return")
    playlist_selector(playlist_arr, xml_root)
    return


def playlist_selector(playlist_array, xml_root):
    user_choice = input("Select playlist number to export: ")
    if user_choice == "E" or user_choice == "e":
        main_menu()
    else:
        try:
            list_single_playlist(xml_root, playlist_array[int(user_choice)])
        except ValueError:
            print("Not valid playlist number")


def list_single_playlist(xml_root, playlist_name):
    print("Searching: " + playlist_name)
    for elem in xml_root.iter("NODE"):
        for playlist in elem.iterfind('NODE[@Name="%s"]' % playlist_name):
            playlist_path = set_playlist_path(playlist_name)
            for track_counter, playlist_track in enumerate(playlist):
                track = get_track_from_collection(
                    playlist_track.attrib["Key"], xml_root
                )
                path = PureWindowsPath(track[1], track[0])
                if path.drive != "" and args.prefix != "":
                    path = Path(args.prefix, *path.parts[1:])
                target_path = Path(
                    playlist_path, str(track_counter).zfill(2) + "_" + path.name
                )
                search_str = str(Path(target_path.name).stem) + ".*"
                exists = sorted(playlist_path.glob(search_str))
                if len(exists) > 0:
                    print(str(target_path) + " already exists")
                elif path.suffix == ".flac":
                    wav_file = convert_to_wav(path, target_path)
                    reencode = check_wave_format(wav_file)
                    if len(reencode) != 0:
                        wav_file = convert_to_wav(path, target_path, reencode)
                elif path.suffix == ".wav":
                    reencode = check_wave_format(path)
                    if len(reencode) != 0:
                        convert_to_wav(path, target_path, reencode)
                    else:
                        copy_file(path, target_path)
                        fix_wav_header(target_path)
                elif path.suffix == ".aif" or path.suffix == ".aiff":
                    reencode = check_aifc_format(path)
                    if len(reencode) != 0:
                        wav_file = convert_to_wav(path, target_path, reencode)
                    else:
                        copy_file(path, target_path)
                else:
                    copy_file(path, target_path)


def copy_file(path, target_path):
    try:
        shutil.copy(path, target_path)
    except IOError:
        print("IO Error")
    return


def get_track_from_collection(trackid, xml_root):
    for track in xml_root.iterfind('COLLECTION/TRACK[@TrackID="%s"]' % trackid):
        track_file = track.attrib["Location"]
        track_file = track_file.replace("file://localhost/", "")
        track_filename_mark = track_file.rfind("/")
        track_path = urllib.parse.unquote(track_file[0:track_filename_mark])
        track_filename = urllib.parse.unquote(
            track_file[track_filename_mark + 1 : len(track_file)]
        )
        print("Track Path raw: " + track_file)
        return (track_filename, track_path)


def set_playlist_path(playlist_name):
    path = Path(args.outpath, playlist_name)
    print("Playlist DIR: " + str(path))
    if not path.exists():
        path.mkdir()
    return path


def convert_to_wav(path, target_path, params=[]):
    target = str(target_path.with_suffix(".wav"))
    if len(params) > 0:
        print(f"Reencoding with parameters {params}")
        subprocess.run(flatten(["ffmpeg", "-y", "-i", path, params, target]))
    else:
        subprocess.run(["ffmpeg", "-y", "-i", path, target])
    fix_wav_header(target)
    return target


def flatten(l):
    return (
        flatten(l[0]) + (flatten(l[1:]) if len(l) > 1 else [])
        if type(l) is list
        else [l]
    )


def open_rb_export():
    if Path(args.exportfile).is_file():
        return ET.parse(args.exportfile)
    else:
        sys.exit()


def check_wave_format(path):
    reencode = []
    with wave.open(str(path), "rb") as wave_file:
        frame_rate = wave_file.getframerate()
        if frame_rate > 48000:
            print(f"Error: Unsupported wave format (smaple rate is {frame_rate})")
            reencode.append("-ar")
            reencode.append("48000")
        bit_depth = wave_file.getsampwidth()
        if bit_depth >= 24:
            print("Bit depth of 24 detected")
            reencode.append("-c:a")
            reencode.append("pcm_s24le")
    return reencode


def check_aifc_format(path):
    reencode = []
    with aifc.open(str(path), "rb") as aifc_file:
        frame_rate = aifc_file.getframerate()
        if frame_rate > 48000:
            print("Error: Unsupported aifc format (smaple rate is " + frame_rate + ")")
            reencode.append("-ar")
            reencode.append("48000")
        bit_depth = aifc_file.getsampwidth()
        if bit_depth >= 24:
            print("Bit depth of 24 detected")
            reencode.append("-c:a")
            reencode.append("pcm_s24le")
    return reencode


def fix_wav_header(path):
    # Idea from: https://github.com/ckbaudio/WavPatcher/blob/main/maintest.py
    with open(path, "rb+") as f:
        f.seek(20, 0)
        formatID = f.read(2)
        bint = int.from_bytes(formatID, byteorder="little", signed=False)
        if bint == 65534:
            print("Found incompatible wav-header, fixing wav-header...")
            f.seek(-2, 1)
            f.write(b"\x01\x00")


def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL)
    except Exception:
        print(f"Please install ffmeg.")
        exit(1)


def main_menu():
    if not Path(args.outpath).exists():
        Path(args.outpath).mkdir()
    print_structure(open_rb_export())


def main():
    parser = argparse.ArgumentParser(
        prog="rek",
        epilog="""
        Copyright, (c) Nico Bucher 2022
        """,
        description="""Rek - A tool to export playlists created in Rekordbox (PIONEER) files without using Rekordbox.
        It is originally based on a script by Marek Pleskac (maaraneasi/RekordExport).
		Additionally, rek offers a few options for the exported files: 
        Flac files can be converted to wav in the process (only few PIONEER devices currently support flac).
        Incompatible wav headers are automatically fixed (happens in some wavs e.g obtained from bandcamp).""",
    )
    parser.add_argument("exportfile", nargs="?")
    parser.add_argument("-o", "--outpath", default=".")
    parser.add_argument("-p", "--prefix", default="")
    parser.add_argument(
        "--no-flac",
        action="store_true",
        help="Convert flac files to wav along the way (requires ffmpeg installed).",
    )
    parser.add_argument(
        "-r",
        "--reencode",
        action="store_true",
        help="Reencode files with sample rates above 48 kHz and unsupported bitrates (requires ffmpeg installed).",
    )
    global args
    args = parser.parse_args()
    check_ffmpeg()
    main_menu()


if __name__ == "__main__":
    main()
