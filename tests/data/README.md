# Test Data

This folder contains sample DLC (DeepLabCut) annotation CSV files for testing.
These files are used to test issue #17: `annotations_to_coco` fails with certain DLC `.csv` files.

## Background

DLC CSV files can store image paths in two formats:

1. **Single-index format**: Path in one column as `labeled-data/folder/filename.png`
2. **Multi-index format**: Path split across 3 columns as `labeled-data,folder,filename.png`

The multi-index format is used by newer DLC versions. The `sleap-io` library expects the single-index format, so `poseinterface` detects and converts multi-index CSVs automatically.

## Files

### CollectedData_Shailaja.csv
- **Format**: Multi-index (3 columns for path)
- **Path structure**: `labeled-data,folder,filename.png`
- **Keypoints**: 40 body parts (mouse face/paws/tail tracking)
- **Source**: Shailaja Akella (Allen Institute)

### CollectedData_Pranav.csv
- **Format**: Single-index (1 column for path)
- **Path structure**: `labeled-data/folder/filename.png`
- **Keypoints**: 4 body parts (snout, leftear, rightear, tailbase)
- **Source**: https://github.com/DeepLabCut/DeepLabCut/tree/main/examples/openfield-Pranav-2018-10-30

## Test Matrix

The test fixtures combine these files with two CSV location options:

| Fixture Name                       | Format       | CSV Location   |
|------------------------------------|--------------|----------------|
| `dlc_single_index_in_video_folder` | Single-index | Video folder   |
| `dlc_single_index_in_project_root` | Single-index | Project root   |
| `dlc_multi_index_in_video_folder`  | Multi-index  | Video folder   |
| `dlc_multi_index_in_project_root`  | Multi-index  | Project root   |

- **Video folder**: CSV in `labeled-data/<video_folder>/` (same directory as frames)
- **Project root**: CSV in the DLC project root directory
