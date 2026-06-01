import argparse
import numpy as np
import uproot
from pathlib import Path


class CompassResultSplitter:
    """
    Split a batch of CoMPASS ROOT TTrees across multiple channels into time-synchronized chunks.

    The splitter preserves the original channel file names and folder structure by creating a
    directory hierarchy of the form:

        <output_dir>/<parent_dir_name>_<duration>/test_<i>/RAW/CH<channel>.root

    Each chunk contains the entries from all channels that fall inside the same time window.
    """

    def __init__(
        self,
        parent_dir: str,
        channels: int,
        output_dir: str,
        duration_sec: float,
        time_unit_factor: float,
        tree_name: str = "Data_R;1",
        timestamp_branch: str = "Timestamp",
    ):
        self.parent_dir = Path(parent_dir).resolve()
        self.channels = channels

        # If no output directory is provided, default to the parent folder of the input directory.
        if output_dir:
            self.output_dir = Path(output_dir).resolve()
        else:
            self.output_dir = self.parent_dir.parent

        self.duration_sec = duration_sec
        self.time_unit_factor = time_unit_factor
        self.tree_name = tree_name
        self.timestamp_branch = timestamp_branch

        # Convert duration from seconds into the same timestamp units used in the ROOT tree.
        self.chunk_duration = duration_sec * time_unit_factor

    def run(self) -> int:
        """Execute the splitter and write the chunked output directories."""

        # Find the expected ROOT files for every channel.
        channel_files = self._locate_files()

        # Determine the number of common, synchronized chunks available across all channels.
        min_chunks = self._calculate_min_chunks(channel_files)

        if min_chunks == 0:
            print("Not enough data to create a full chunk. Exiting.")
            return 0

        # Create one top-level output directory per requested duration.
        main_out_dir = self.output_dir / f"{self.parent_dir.name}_{round(self.duration_sec)}"
        main_out_dir.mkdir(parents=True, exist_ok=True)

        # Pre-create the per-chunk RAW directories so each channel can write into a matching structure.
        chunk_dirs = []
        for i in range(min_chunks):
            d = main_out_dir / f"test_{i}" / "RAW"
            d.mkdir(parents=True, exist_ok=True)
            chunk_dirs.append(d)

        # Split each channel file into the computed set of time windows.
        for ch_id, filepath in channel_files.items():
            self._split_channel(filepath, chunk_dirs, min_chunks)

        print(f"\nDone! Output directories generated in:\n  {main_out_dir}")
        return min_chunks

    def _locate_files(self) -> dict:
        """Find the expected ROOT files for each channel inside the parent RAW directory."""
        raw_dir = self.parent_dir / "RAW"
        if not raw_dir.exists() or not raw_dir.is_dir():
            raise FileNotFoundError(f"RAW directory not found at {raw_dir}")

        channel_files = {}
        all_root_files = list(raw_dir.glob("*.root"))

        for ch in range(self.channels):
            token = f"CH{ch}"
            matched = [f for f in all_root_files if token in f.name]

            if not matched:
                raise FileNotFoundError(f"No file containing '{token}' found in {raw_dir}")
            if len(matched) > 1:
                raise ValueError(f"Ambiguity error: Multiple files containing '{token}' found.")

            channel_files[ch] = matched[0]

        return channel_files

    def _calculate_min_chunks(self, channel_files: dict) -> int:
        """Compute the number of synchronized chunks available across every channel."""
        chunk_counts = []

        for ch_id, filepath in channel_files.items():
            with uproot.open(f"{filepath}:{self.tree_name}") as tree:
                num_entries = tree.num_entries
                if num_entries == 0:
                    chunk_counts.append(0)
                    continue

                start_time = tree[self.timestamp_branch].array(
                    library="np", entry_start=0, entry_stop=1
                )[0]

                end_time = tree[self.timestamp_branch].array(
                    library="np", entry_start=num_entries - 1, entry_stop=num_entries
                )[0]

                chunks = 0
                curr = start_time
                while curr < end_time:
                    chunks += 1
                    curr += self.chunk_duration

                chunk_counts.append(chunks)

        # Use the minimum across channels so every chunk is present in every channel.
        return min(chunk_counts) if chunk_counts else 0

    def _split_channel(self, filepath: Path, chunk_dirs: list, num_chunks: int):
        """Write each channel file into time-aligned chunk files based on the timestamp branch."""
        with uproot.open(f"{filepath}:{self.tree_name}") as tree:
            timestamps = tree[self.timestamp_branch].array(library="np")
            total_entries = len(timestamps)

            current_start_time = timestamps[0]

            for i in range(num_chunks):
                current_end_time = current_start_time + self.chunk_duration

                start_entry = np.searchsorted(timestamps, current_start_time, side="left")
                stop_entry = np.searchsorted(timestamps, current_end_time, side="right")
                stop_entry = min(stop_entry, total_entries)

                out_filename = chunk_dirs[i] / filepath.name

                if start_entry == stop_entry:
                    current_start_time = current_end_time
                    continue

                print(
                    f"  -> Chunk {i}: Entries "
                    f"[{start_entry} to {stop_entry}] "
                    f"to {chunk_dirs[i].parent.name}/RAW/{filepath.name}"
                )

                # Read the selected entries from the tree. Uproot defaults to awkward arrays,
                # which handle variable-length waveforms correctly.
                chunk_data = tree.arrays(
                    entry_start=start_entry,
                    entry_stop=stop_entry
                )

                # Convert the awkward record array to a simple dict so the output ROOT tree can be created cleanly.
                tree_dict = {field: chunk_data[field] for field in chunk_data.fields}

                # Strip cycle suffixes from the tree name for the output file.
                clean_tree_name = self.tree_name.split(";")[0]

                with uproot.recreate(out_filename) as out_file:
                    out_file.mktree(clean_tree_name, tree_dict)

                current_start_time = current_end_time


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Split multiple CoMPASS ROOT files across channels into "
            "synchronized, fixed-duration time windows while preserving folder structure."
        )
    )

    parser.add_argument(
        "parent_dir",
        help="Input parent directory (must contain a 'RAW' subdirectory)",
    )

    parser.add_argument(
        "n_channels",
        type=int,
        help="Total number of channels to parse (expects files matching CH0 to CH[N-1])",
    )

    parser.add_argument(
        "duration",
        type=float,
        help="Duration of each chunk in seconds",
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        default=None,
        help="Target overarching output directory (default: same location as parent_dir)",
    )

    parser.add_argument(
        "-t",
        "--tree-name",
        default="Data_R;1",
        help="TTree name (default: %(default)s)",
    )

    parser.add_argument(
        "--time-unit-factor",
        type=float,
        default=1e12,
        help=(
            "Timestamp units per second. "
            "Use 1e12 for picoseconds, 1e9 for nanoseconds "
            "(default: %(default)s)"
        ),
    )

    parser.add_argument(
        "--timestamp-branch",
        default="Timestamp",
        help="Timestamp branch name (default: %(default)s)",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    splitter = CompassResultSplitter(
        parent_dir=args.parent_dir,
        channels=args.n_channels,
        output_dir=args.output_dir,
        duration_sec=args.duration,
        time_unit_factor=args.time_unit_factor,
        tree_name=args.tree_name,
        timestamp_branch=args.timestamp_branch,
    )

    splitter.run()


if __name__ == "__main__":
    main()
