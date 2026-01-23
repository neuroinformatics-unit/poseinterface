# Test Data

This folder contains sample DLC (DeepLabCut) annotation CSV files for testing.
These files are used to debug issue #17: `annotations_to_coco` fails with certain DLC `.csv` files.

## Files

### CollectedData_Shailaja.csv
- **Path structure**: `labeled-data,folder,filename.png` (path components separated by commas)
- **Header columns**: empty columns before keypoint data (`scorer,,,Shailaja,...`)
- **Keypoints**: 40 body parts (mouse face/paws/tail tracking)
- **Source**: Shailaja Akella (Allen Institute)

### CollectedData_Loukia.csv
- **Path structure**: `labeled-data,folder,filename.png` (path components separated by commas)
- **Header columns**: empty columns before keypoint data (`scorer,,,Loukia,...`)
- **Keypoints**: 20 body parts (mouse + EPM maze corners)
- **Source**: Loukia Katsouri (Sainsbury Wellcome Centre)

### CollectedData_Pranav.csv
- **Path structure**: `labeled-data/folder/filename.png` (slashes)
- **Header columns**: Data starts immediately after path (`scorer,Pranav,...`)
- **Keypoints**: 4 body parts (snout, leftear, rightear, tailbase)
- **Source**: https://github.com/DeepLabCut/DeepLabCut/tree/main/examples/openfield-Pranav-2018-10-30

## Key Differences

| File     | Path separator |
|----------|----------------|
| Shailaja | commas         |
| Loukia   | commas         |
| Pranav   | slashes        |
