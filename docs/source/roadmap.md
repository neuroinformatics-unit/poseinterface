# Roadmap

This page outlines **current development priorities** and aims to **guide core
developers** and to **encourage community contributions**. It is a living
document and will be updated as the project evolves.

The roadmap is **not meant to limit** `poseinterface` features, as we are open
to suggestions and contributions.
Join our [Zulip chat](https://neuroinformatics.zulipchat.com/) to share your
ideas.
We will take community feedback into account when planning future releases.

## Long-term vision

The following capabilities are guiding the project's direction:

- **Standardize the representation of pose estimation datasets.**
  Labeled frames, labeled video clips, unlabeled video, and experimental
  metadata should all be representable, queryable, and validatable in a single,
  consistent, machine-readable schema, regardless of which tool produced them.
- **Interoperate with leading pose estimation tools.**
  We aim to bring datasets from Lightning Pose, DeepLabCut, SLEAP, and others
  into the standardized schema without loss of label fidelity or the need for
  re-annotation.
- **Grow a shared, community-contributed benchmark corpus.**
  Labs should be able to submit labeled and unlabeled data with minimal
  friction, expanding the pool of data available for training and evaluating
  pose estimation and point tracking models.
- **Expose agent-callable, AI-native interfaces.**
  Automated pipelines and AI agents should be able to run inference and train
  models on standardized data directly, without a human in the loop.
- **Define shared keypoint ontologies.** A common vocabulary for body parts
  across labs' differing naming conventions should make it possible to combine
  data from multiple independent datasets into a single training set, starting
  with mice and expanding to other species over time.
- **Support multi-animal and multi-camera datasets.** The schema and tooling
  should extend naturally beyond single-animal, single-camera use cases.

## Focus areas for 2026

- Complete and publish a versioned data specification for single-animal,
  single-camera pose estimation datasets (images, videos, labels, experimental
  metadata), building on our existing draft schema.
- Validate the schema against a range of real-world experimental paradigms
  (e.g., head-fixed vs. freely moving, multiple species).
- Build a converter from Lightning Pose project exports into the standardized
  schema, plus submission utilities for contributing datasets to the benchmark
  corpus.
- Build converters from DeepLabCut and SLEAP project exports into the
  standardized schema, sharing code with the Lightning Pose converter where
  possible.
- Define and document a stable, agent-callable programmatic interface for
  running Lightning Pose **inference** on raw video via PoseInterface.
- Define or adapt a shared keypoint ontology for mouse body parts, and map
  keypoint labels across contributed benchmark datasets onto it.
- Host tutorials on dataset conversion and submission to the benchmark corpus.

## Focus areas for 2025

We defined these high-level goals in 2025. Items completed have been checked
off.

- [x] Establish the core `poseinterface` framework: standardized folder
      structures, file formats, and naming conventions for benchmark datasets.
- [x] Release the package on [PyPI](https://pypi.org/project/poseinterface/).
- [x] Launch a public
      [documentation website](https://poseinterface.neuroinformatics.dev/).
- [x] Publish contributing guidelines and a Code of Conduct.
- [x] Draft an initial
      [benchmark dataset specification](https://poseinterface.neuroinformatics.dev/benchmark-dataset.html),  # noqa
      including early design decisions such as reliance on COCO-style JSON.
- [ ] Define and document a stable programmatic interface for **training**
      Lightning Pose models via PoseInterface.
- [ ] Train a Lightning Pose model across multiple mapped datasets from the
      benchmark corpus, as a proof of concept for cross-dataset training.

## Out of scope for now

- Hosting infrastructure/leaderboard for a benchmark competition.
- Full two-way training/inference integration with DeepLabCut and SLEAP
  (the API is being designed to make this easier to add later).
- Support for multi-view and multi-animal datasets

---

Feedback and discussion are welcome via
[issues](https://github.com/neuroinformatics-unit/poseinterface/issues)
or our [Zulip chat](https://neuroinformatics.zulipchat.com/).
