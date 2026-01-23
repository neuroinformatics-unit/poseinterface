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

### CollectedData_Loukia.csv
- **Format**: Multi-index (3 columns for path)
- **Path structure**: `labeled-data,folder,filename.png`
- **Keypoints**: 20 body parts (mouse + EPM maze corners)
- **Source**: Loukia Katsouri (Sainsbury Wellcome Centre)

### CollectedData_Pranav.csv
- **Format**: Single-index (1 column for path)
- **Path structure**: `labeled-data/folder/filename.png`
- **Keypoints**: 4 body parts (snout, leftear, rightear, tailbase)
- **Source**: https://github.com/DeepLabCut/DeepLabCut/tree/main/examples/openfield-Pranav-2018-10-30

## Summary

| File     | Format       | Path columns |
|----------|--------------|--------------|
| Shailaja | Multi-index  | 3            |
| Loukia   | Multi-index  | 3            |
| Pranav   | Single-index | 1            |
