# Roadmap

This page outlines **current development priorities** and aims to **guide core
developers** and to **encourage community contributions**. It is a living
document and will be updated as the project evolves.

The roadmap is **not meant to limit** `poseinterface` features, as we are open
to suggestions and contributions.
Join our [Zulip chat](https://neuroinformatics.zulipchat.com/#narrow/channel/617946-PoseInterface)
to share your ideas.
We will take community feedback into account when planning future releases.

## Long-term vision

The following capabilities are guiding the project's direction:

- **Standardize the representation of keypoint datasets.**
  Labeled frames, labeled video clips, unlabeled video, and experimental
  metadata should all be representable, queryable, and validatable in a single,
  consistent, machine-readable schema, regardless of which tool produced them.
- **Interoperate with leading keypoint tracking tools.**
  We aim to bring datasets from pose estimation packages like
  [Lightning Pose](https://lightning-pose.readthedocs.io/),
  [DeepLabCut](https://www.mackenziemathislab.org/deeplabcut),
  [SLEAP](https://sleap.ai/),
  and others into the standardized schema without loss of label fidelity or the
  need for re-annotation.
  Labeled video clips will also allow interoperability with point tracking
  models like
  [TAPIR](https://deepmind-tapir.github.io/)
  and
  [CoTracker](https://co-tracker.github.io/).
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

## Focus areas for 2027

- Complete and publish a versioned data specification for single-animal,
  single-camera pose estimation datasets (images, videos, labels, experimental
  metadata), building on our existing draft schema.
- Validate the schema against a range of real-world experimental paradigms
  (e.g., head-fixed vs. freely moving, multiple species).
- Build converters from DeepLabCut and SLEAP project exports into the
  standardized schema, sharing code with the Lightning Pose converter where
  possible.
- Define or adapt a shared keypoint ontology for mouse body parts, and map
  keypoint labels across contributed benchmark datasets onto it.
- Host tutorials on dataset conversion and submission to the benchmark corpus.
- Define and document a stable programmatic interface for **training**
  Lightning Pose models via `poseinterface`.
- Train a Lightning Pose model across multiple mapped datasets from the
  benchmark corpus, as a proof of concept for cross-dataset training.
- Define and document a stable, agent-callable programmatic interface for
  running **inference** with additional point trackers on raw video via
  `poseinterface` (for instance TAPIR).

## Focus areas for 2026

We defined these high-level goals at the end of 2025.
Items completed have been checked off.

- [x] Establish the core `poseinterface` framework: standardized folder
      structures, file formats, and naming conventions for benchmark datasets.
- [x] Release the package on [PyPI](https://pypi.org/project/poseinterface/).
- [x] Launch a public
      [documentation website](https://poseinterface.neuroinformatics.dev/).
- [x] Publish contributing guidelines and a Code of Conduct.
- [x] Draft an initial
      [benchmark dataset specification](https://poseinterface.neuroinformatics.dev/benchmark-dataset.html),
      including early design decisions such as reliance on COCO-style JSON.
- [ ] Build a converter from Lightning Pose project exports into the
      standardized schema, plus submission utilities for contributing datasets
      to the benchmark corpus.
- [ ] Define standardized evaluation metrics for pose estimators and
      point trackers.
- [ ] Define and document a stable, agent-callable programmatic interface for
      running Lightning Pose **inference** on raw video via `poseinterface`
      (i.e., initial implementation of one pose estimator).
- [ ] Define and document a stable, agent-callable programmatic interface for
      running CoTracker **inference** on raw video via `poseinterface`
      (i.e., initial implementation of one point tracker).

## Planned for later

- Hosting infrastructure/leaderboard for a benchmark competition.
- Full two-way training/inference integration with DeepLabCut and SLEAP
  (the API is being designed to make this easier to add later).
- Support for multi-camera and multi-animal datasets.

---

Feedback and discussion are welcome via
[issues](https://github.com/neuroinformatics-unit/poseinterface/issues)
or our [Zulip chat](https://neuroinformatics.zulipchat.com/#narrow/channel/617946-PoseInterface).
