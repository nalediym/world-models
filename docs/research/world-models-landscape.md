# World Models Landscape: A Research Overview

A curated collection of cutting-edge world model research spanning robotics, video generation, and embodied AI.

---

## Table of Contents

1. [Leading Research Labs & Projects](#leading-research-labs--projects)
2. [Robot World Models](#robot-world-models)
   - [DreamDojo (NVIDIA)](#dreamdojo-nvidia)
   - [1X World Model](#1x-world-model)
   - [DreamZero (NVIDIA)](#dreamzero-nvidia)
   - [Rhoda AI DVA](#rhoda-ai-dva)
3. [City-Scale World Models](#city-scale-world-models)
   - [Seoul World Model](#seoul-world-model)
4. [Digital/UI World Models](#digitalui-world-models)
   - [UI-Simulator](#ui-simulator)
5. [Evaluation & Benchmarks](#evaluation--benchmarks)
   - [Stable-WorldModel-v1](#stable-worldmodel-v1)
6. [The Bitter Lesson Reminder](#the-bitter-lesson-reminder)

---

## Leading Research Labs & Projects

| Project/Lab | Organization | Focus Area |
|-------------|--------------|------------|
| **World Labs Research** | Fei-Fei Li's startup | Spatial intelligence, 3D world understanding |
| **Genie 3** | Google DeepMind | Generative interactive environments |
| **Dreamer 4** | DeepMind | Reinforcement learning world models |
| **Verses AI** | Verses | Active inference, spatial web |
| **DreamDojo** | NVIDIA | Robot world models from human videos |
| **DreamZero** | NVIDIA | Zero-shot robot policies |
| **1X World Model** | 1X Technologies | Humanoid robot world models |
| **Rhoda AI** | Rhoda | Direct Video-Action models |
| **Seoul World Model** | NAVER/KAIST | City-scale world simulation |
| **UI-Simulator** | UCLA/Harvard | Digital agent world models |

---

## Robot World Models

### DreamDojo (NVIDIA)

**DreamDojo: A Generalist Robot World Model from Large-Scale Human Videos**

🔗 [Website](https://dreamdojo-world.github.io/) | [Paper](https://arxiv.org/abs/2602.06949) | [Code](https://github.com/NVIDIA/DreamDojo)

**Key Innovation:** A generalist robot world model trained on **44,000 hours** of diverse human egocentric videos—the largest dataset to date for world model pretraining.

#### Highlights

1. **Large-scale video dataset**: 44k hours of diverse human egocentric videos (15x longer, 96x more skills, 2,000x more scenes than previous largest datasets)
2. **Foundation world model**: First robot world model demonstrating strong generalization to diverse objects and environments after post-training
3. **Distillation pipeline**: Achieves long-horizon autoregressive generation with stable real-time interactions at **10 FPS for over 1 minute**

#### Method Overview

DreamDojo uses a two-stage approach:
- **Pre-training** with latent actions on large-scale human datasets to acquire comprehensive physical knowledge
- **Post-training** on the target embodiment with continuous robot actions

#### Key Results

- **Object & Environment Generalization**: Produces realistic action-conditioned rollouts for GR-1, G1, AgiBot, and YAM robots across wide range of environments
- **Real-Time Performance**: 10 FPS generation through autoregressive few-step distillation
- **Applications**: Live teleoperation, policy evaluation, model-based planning

#### Citation

```bibtex
@article{gao2026dreamdojo,
    title={DreamDojo: A Generalist Robot World Model from Large-Scale Human Videos},
    author={Gao, Shenyuan and Liang, William and Zheng, Kaiyuan and Malik, Ayaan and Ye, Seonghyeon and Yu, Sihyun and Tseng, Wei-Cheng and Dong, Yuzhu and Mo, Kaichun and Lin, Chen-Hsuan and Ma, Qianli and Nah, Seungjun and Magne, Loic and Xiang, Jiannan and Xie, Yuqi and Zheng, Ruijie and Niu, Dantong and Tan, You Liang and Zentner, K.R. and Kurian, George and Indupuru, Suneel and Jannaty, Pooya and Gu, Jinwei and Zhang, Jun and Malik, Jitendra and Abbeel, Pieter and Liu, Ming-Yu and Zhu, Yuke and Jang, Joel and Fan, Linxi "Jim"},
    journal={arXiv preprint arXiv:2602.06949},
    year={2026}
}
```

---

### 1X World Model

**From Video to Action: A New Way Robots Learn**

🔗 [Website](https://www.1x.tech/discover/world-model-self-learning)

**Key Innovation:** Video-pretrained world model (1XWM) integrated into NEO humanoid robot as a policy, deriving actions from text-conditioned video generation rather than direct action prediction.

#### Core Approach

Unlike Vision-Language-Action (VLA) models that predict action trajectories from static image-language input, 1XWM:
1. **World Model Backbone**: 14B generative video model trained on web-scale video, mid-trained on egocentric human data, fine-tuned on NEO sensorimotor logs
2. **Inverse Dynamics Model (IDM)**: Bridges pixels to actuators by predicting exact action sequences to transition between generated frames

#### Training Recipe

1. **Egocentric Mid-training**: 900 hours of egocentric human video for first-person manipulation alignment
2. **Embodiment Fine-tuning**: 70 hours of robot data to adapt to NEO's visual appearance and kinematics
3. **Caption Upsampling**: VLM-generated detailed captions for better prompt adherence

#### Capabilities

- **Zero-shot generalization** to novel objects, motions, and tasks without pre-training on large-scale robot data
- **Task success rates**: Steam shirt (80%), Grab chips (70%), Sliding door (60%), Iron shirt (50%), Watering can (40%)
- **Best-of-N sampling**: 8 parallel generations improve success from 30% → 45% on pull tissue task

#### Key Insights

> "Hardware as a first-class citizen in the AI stack closes the human-robot translation gap. By combining embodiment with human-like compliance, interaction dynamics often match human motion closely enough for the model's learned priors to remain in distribution."

**Inference Speed**: 11 seconds per 5-second video generation (multi-GPU), with 1 second for IDM action extraction

---

### DreamZero (NVIDIA)

**World Action Models are Zero-shot Policies**

🔗 [Website](https://dreamzero0.github.io/) | [Paper](https://arxiv.org/abs/2602.15922) | [Code](https://github.com/dreamzero0/dreamzero) | [Eval Gallery](https://dreamzero0.github.io/evals_gallery)

**Key Innovation:** World Action Model (WAM) built on pretrained video diffusion that jointly predicts future world states AND actions—achieving **2× improvement** in generalization to new tasks and environments compared to state-of-the-art VLAs.

#### Core Concept

Unlike VLAs that excel at semantic generalization but struggle with unseen physical motions, DreamZero:
- Jointly models video and action using video as dense representation of world evolution
- Learns diverse skills from heterogeneous robot data without repetitive demonstrations
- Enables **real-time closed-loop control at 7Hz** with 14B autoregressive video diffusion model

#### Six Evaluation Settings

1. **AgiBot Pretraining**: 10 seen + 10 unseen tasks, zero-shot in novel environments
2. **DROID Pretraining**: Franka robot, 20 seen + 20 unseen tasks with unseen verbs
3. **Post-Training**: Fine-tuning on 3 downstream tasks while retaining OOD robustness
4. **New Embodiment Adaptation**: Adapts to YAM robot with only **30 minutes of play data** (55 trajectories)
5. **Interactive Prompting**: Zero-shot prompting in the wild
6. **Real-Time Inference**: 38× speedup through optimizations

#### Key Results

| Setting | DreamZero | Best VLA Baseline |
|---------|-----------|-------------------|
| AgiBot Seen Tasks | 62.2% | 27.4% |
| AgiBot Unseen Tasks | 39.5% | Near-zero |
| DROID Unseen Verbs | 49% | 25-32% |

**Cross-embodiment transfer**: Video-only demonstrations from humans/other robots yield **42% improvement** on unseen tasks with just 10-20 minutes of data.

#### Real-Time Performance

- **DreamZero-Flash**: Optimized variant running at 150ms per action chunk (7Hz)
- Single-step inference maintains performance with minimal quality loss
- Asynchronous inference + action chunk smoothing for smooth execution

#### Citation

```bibtex
@misc{ye2026worldactionmodelszeroshot,
    title={World Action Models are Zero-shot Policies},
    author={Ye, Seonghyeon and Ge, Yunhao and Zheng, Kaiyuan and Gao, Shenyuan and Yu, Sihyun and Kurian, George and Indupuru, Suneel and Tan, You Liang and Zhu, Chuning and Xiang, Jiannan and Malik, Ayaan and Lee, Kyungmin and Liang, William and Ranawaka, Nadun and Gu, Jiasheng and Xu, Yinzhen and Wang, Guanzhi and Hu, Fengyuan and Narayan, Avnish and Bjorck, Johan and Wang, Jing and Kim, Gwanghyun and Niu, Dantong and Zheng, Ruijie and Xie, Yuqi and Wu, Jimmy and Wang, Qi and Julian, Ryan and Xu, Danfei and Du, Yilun and Chebotar, Yevgen and Reed, Scott and Kautz, Jan and Zhu, Yuke and Fan, Linxi "Jim" and Jang, Joel},
    year={2026},
    eprint={2602.15922},
    archivePrefix={arXiv},
    primaryClass={cs.RO}
}
```

---

### Rhoda AI DVA

**Causal Video Models Are Data-Efficient Robot Policy Learners**

🔗 [Website](https://www.rhoda.ai/research/direct-video-action)

**Key Innovation:** Direct Video-Action Model (DVA) that reformulates robot policies as video generation, achieving data-efficient task learning with as little as **~10 hours** of robot data.

#### Direct Video-Action Model (DVA) Architecture

```
Video Context → Causal Video Model → Generated Video → 
Inverse Dynamics Model → Generated Actions → Robot Execution
```

The cycle repeats in a streaming closed-loop, running multiple times per second.

#### Key Advantages

1. **Data-efficient task learning**: Complex, long-horizon tasks with ~10 hours of robot data
2. **Long-context visual memory**: Hundreds of frames of visual context (vs. few frames in VLAs)
3. **One-shot learning**: Imitate human behavior from single demonstration at test time
4. **Interpretability**: Robot behavior visualized through autoregressive rollouts

#### Native Causal Video Models

- **Context Amortization**: Training strategy predicting future video at every position in sequence for efficient training
- Pre-trained from scratch as causal video model (not distilled from bi-directional model)
- KV-caching for efficient inference with real observations as context

#### Leapfrog Inference

A strategy for continuous robot control:
- Predicts long enough into future to cover next prediction's inference latency
- Conditioned on action currently being executed (from previous timestep)
- Ensures trajectory continuity despite stochastic generative model

#### Real-World Tasks (Customer Deployments)

**Decanting Task** (11 hours of data):
- Unpack boxes, decant bearings, sort packaging
- Complex bimanual manipulation with edge cases (broken straps, ripped bags)
- Operated autonomously for **1.5 hours** without intervention

**Container Breakdown** (17 hours of data):
- Break down 50-pound Contico containers
- Handle diverse debris and partial observability
- Operated for **160 minutes** continuously

#### Long-Context Capabilities

- **Shell Game**: Tracks hidden objects across multiple swaps using persistent visual memory
- **Returns Processing**: End-to-end un-package, inspect, fold, repackage with no hand-engineered subtask scaffolding
- **One-shot Demo Following**: Extrapolates from single human demonstration to novel objects/environments

---

## City-Scale World Models

### Seoul World Model

**Grounding World Simulation Models in a Real-World Metropolis**

🔗 [Website](https://seoul-world-model.github.io/) | [Paper](https://arxiv.org/abs/2603.15583) | [Code](https://github.com/naver-ai/seoul-world-model)

**Key Innovation:** City-scale world model grounded in the actual streets of Seoul, generating faithful videos spanning **multi-kilometer** trajectories through retrieval-augmented generation.

#### Capabilities

1. **Multi-kilometer Trajectories**: Generates videos over kilometers without accumulating errors
2. **Free-Form Navigation**: Supports arbitrary camera trajectories (sidewalks, highways, corners)
3. **Text-Prompted Scenarios**: Reshape scenes with prompts ("massive wave on streets", "Godzilla between skyscrapers")
4. **RAG with Street-View Database**: Retrieves nearby street-view images for geometric/appearance conditioning

#### Data

- **1.2M real panoramic images** captured across Seoul
- **10K synthetic videos** from CARLA simulator (431,500m² coverage)
- **Cross-temporal pairing**: Reference images from different times to focus on persistent structure
- **View interpolation**: Synthesizes smooth training videos from sparse keyframes

#### Virtual Lookahead Sink

Novel mechanism to stabilize long-horizon generation:
- Dynamically retrieves nearest street-view image as virtual future destination
- Provides clean, error-free anchor ahead of current chunk
- Continuously re-grounds generation over hundreds of meters

#### Applications

- Autonomous driving simulation
- Urban planning
- Virtual tourism
- Film/game production

---

## Digital/UI World Models

### UI-Simulator

**LLMs as Scalable, General-Purpose Simulators For Evolving Digital Agent Training**

🔗 [Website](https://ui-simulator.notion.site/llms-as-scalable-digital-world-simulator) | [Paper](https://arxiv.org/abs/2510.14969) | [Code](https://github.com/WadeYin9712/UI-Simulator) | [Models](https://huggingface.co/UI-Simulator)

**Key Innovation:** LLM-based digital world simulator that generates structured UI states and transitions, enabling scalable synthesis of training trajectories for digital agents without expensive human annotation.

#### Core Approach

Digital world model built on LLMs that:
- Simulates UI environment dynamics (web, mobile, computer)
- Generates structured accessibility trees with textual content, spatial coordinates, dynamic attributes
- Uses hybrid rule-based + model-based transitions

#### Two Simulation Modes

**Retrieval-Free Simulation:**
1. Predict overview of next state (high-level description)
2. Generate rich draft in natural language (diverse content)
3. Convert to structured format with assigned coordinates

**Retrieval-Augmented Simulation (UI-Simulator-R):**
- Conditions generation on limited experience from test environment
- Hybrid retrieval: BM25 coarse filtering → GPT-4o semantic retriever → composite selection
- Grounds simulation in prior experience while creating novel UI states

#### UI-Simulator-Grow: Targeted Scaling

Strategic data synthesis paradigm:
1. **Target Task Selection**: Selects tasks with high learning potential (25%-75% loss percentile)
2. **Synthesize Variants**: Lightweight task rewriting preserving core logic
3. **Continual Learning**: Replay strategy with Sentence Transformer-based representative selection

#### Results

| Model | WebArena | AndroidWorld |
|-------|----------|--------------|
| GPT-4o | 13.10% | 11.7% |
| UI-Simulator-R (8B) | 6.40% | 12.9% |
| UI-Simulator-Grow (8B) | 7.14% | 13.4% |

**Key Achievement**: UI-Simulator-Grow matches Llama-3-70B-Instruct using only Llama-3-8B-Instruct with 66% of training trajectories.

#### Advantages

- **Robustness**: Agents trained on simulated environments more robust to UI perturbations
- **Novelty**: Can generate trajectories infeasible to obtain from real environments (search failures, account restrictions)
- **Scalability**: Overcomes infra bottlenecks of parallel real UI environments

---

## Evaluation & Benchmarks

### Stable-WorldModel-v1

**Reproducible World Modeling Research and Evaluation**

🔗 [Paper](https://arxiv.org/abs/2602.08968)

**Key Contribution:** Modular, tested, and documented world-model research ecosystem addressing reproducibility crisis in world model research.

#### Problem Statement

> "Despite recent interest in World Models, most available implementations remain publication-specific, severely limiting their reusability, increasing the risk of bugs, and reducing evaluation standardization."

#### Features

- Efficient data-collection tools
- Standardized environments
- Planning algorithms
- Baseline implementations
- **Controllable factors of variation** (visual and physical properties) for robustness and continual learning research

#### Environments

Each environment enables controlled variation of:
- Visual properties
- Physical properties
- Task configurations

#### Demonstrated Use Case

Used to study zero-shot robustness in DINO-WM (visual world model with DINO representations).

#### Authors

Lucas Maes, Quentin Le Lidec, Dan Haramati, Nassim Massaudi, Damien Scieur, **Yann LeCun**, **Randall Balestriero**

---

## The Bitter Lesson Reminder

🔗 [The Bitter Lesson by Rich Sutton](http://www.incompleteideas.net/IncIdeas/BitterLesson.html)

The recurring theme across all these world model approaches echoes **Rich Sutton's "The Bitter Lesson"** (2019):

> "The biggest lesson that can be read from 70 years of AI research is that general methods that leverage computation are ultimately the most effective, and by a large margin."

### Key Principles Applied

1. **Leverage Scale**: All successful world models rely on massive pre-training (web-scale video, 44k hours of human data)

2. **Search & Learning over Human Knowledge**: Rather than hand-engineering physics or rules, these models learn dynamics directly from data:
   - DreamDojo: "Video as dense representation of how world evolves"
   - 1XWM: "Internet video implicitly encodes structural priors of reality"
   - Rhoda DVA: "Web video is the most scalable data source capturing dynamic physical world"

3. **General Methods**: Video generation as universal interface:
   - Works across robot embodiments (humanoid, industrial arms)
   - Transfers between human and robot (DreamZero: 30 min adaptation)
   - Applies to digital agents (UI-Simulator) and cities (Seoul World Model)

4. **Compute Leverage**: 
   - 14B parameter video diffusion models
   - Multi-GPU inference for real-time control
   - Retrieval-augmented generation for grounding

### The Meta-Lesson

> "We want AI agents that can discover like we can, not which contain what we have discovered. Building in our discoveries only makes it harder to see how the discovering process works."

These world models embody this lesson—they don't encode human physics knowledge, but learn to predict from raw sensory experience (video), enabling them to discover their own understanding of how the world works.

---

## Additional Research (March 2026 Update)

### World Labs - Spatial Intelligence

**From Words to Worlds: Spatial Intelligence is AI's Next Frontier**

🔗 [Website](https://www.worldlabs.ai/blog)

**Key Innovation:** Founded by Fei-Fei Li, World Labs is building "spatial intelligence" — AI that perceives, reasons about and acts within 3D space.

> "**3D is becoming the universal interface for space**. It's the medium that allows humans and AI systems to generate, edit, simulate, and share worlds together."

**Key Products:**
- **Marble**: Frontier multimodal world model (launched Nov 2025)
- **World API**: Public API for generating explorable 3D worlds from text, images, and video
- **RTFM**: Real-Time Frame Model — generates video in real-time as you interact with it (Oct 2025)

**Vision:**
> "Spatial intelligence will let machines truly understand and interact with our physical world" — Fei-Fei Li

---

### Genie 3 (Google DeepMind) - Interactive World Generation

**Generate and Explore Interactive Worlds**

🔗 [Website](https://deepmind.google/models/genie/)

**Key Innovation:** First real-time, interactive world model that generates photorealistic worlds from simple text descriptions.

> "**Genie 3 is the first real-time, interactive world model that generates photorealistic worlds from a simple text description.**"

**Capabilities:**
- **Real-time**: 20-24 frames per second fluid interaction
- **Interactive and controllable**: Generates worlds from text, user controls exploration
- **Photorealistic quality**: 720p resolution with rich visual detail
- **World consistency**: Previously seen details recalled when revisited; handles sustained interaction without degrading
- **Auto-regressive**: Created frame by frame based on world description and user actions

**Key Technical Achievement:**
> "The environments remain largely consistent for several minutes, with memory recalling changes from specific interactions for up to a minute."

**Promptable World Events:**
> "Genie 3 enables a more expressive form of text-based interaction... it possible to change the generated world – such as altering weather conditions or introducing new objects and characters."

**Applications:**
- Gaming (infinite diverse worlds)
- Education (explore historical eras like Ancient Rome)
- Autonomous vehicle training (realistic scenarios in safe setting)
- Embodied agent research (training SIMA agents in Genie worlds)

**Architectural Insight:**
> "For real-time interactivity, this needs to happen multiple times per second in response to user instructions."

---

### Dreamer 4 (Hafner, Yan, Lillicrap)

**Training Agents Inside of Scalable World Models**

🔗 [Paper](https://arxiv.org/abs/2509.24527) | [Website](https://danijar.com/dreamer4/)

**Key Innovation:** Scalable agent that learns to solve control tasks by reinforcement learning inside of a fast and accurate world model — first agent to obtain diamonds in Minecraft purely from offline data.

> "**World models learn general knowledge from videos and simulate experience for training behaviors in imagination, offering a path towards intelligent agents.**"

**Breakthrough:**
> "By learning behaviors in imagination, **Dreamer 4 is the first agent to obtain diamonds in Minecraft purely from offline data, without environment interaction.**"

**Technical Architecture:**
- **Shortcut forcing objective** for real-time interactive inference
- **Efficient transformer architecture**
- Runs on **single GPU** in real-time
- Learns general action conditioning from **only a small amount of data**
- Extracts majority of knowledge from **diverse unlabeled videos**

**The Challenge:**
> "Obtaining diamonds in Minecraft from only offline data, aligning with practical applications such as robotics where learning from environment interaction can be unsafe and slow. This task requires choosing sequences of over 20,000 mouse and keyboard actions from raw pixels."

**Key Insight:**
Previous world models "have been unable to accurately predict object interactions in complex environments." Dreamer 4 achieves this at scale.

---

### VERSES AI / Genius - Active Inference World Models

**Genius: Brainpower for Agents**

🔗 [Website](https://www.verses.ai/blog/genius-can-sense-think-act-and-share-intelligently)

**Key Innovation:** Alternative paradigm to deep learning — using **active inference** and **hierarchical Bayesian models** instead of neural networks.

**Four Core Modules:**

#### SENSE - Perception
> "SENSE makes live vision feasible on edge devices... treats perception more like our own five senses, integrating vision, motion, touching, and acceleration into a picture of what's happening."

Uses **Variational Bayes Gaussian Splatting (VBGS)**:
> "Builds a 3D world from billions of tiny probabilistic Gaussians—each storing color, shape, and position. As new evidence arrives, these blobs shift and refine, letting the system update its map in real time."

> "Every signal—color, shape, position—sharpens the existing model and enables SENSE to maintain a map of the world—in other words, **a world model that gets more accurate with every glimpse**."

#### THINK - AXIOM "Digital Brain"
Mirrors brain structure with mixture models:

| AXIOM Module | Function | Brain Region |
|--------------|----------|--------------|
| Slot Mixture Model (sMM) | Vision: converts pixels to objects | Occipital Lobe |
| Identity Mixture Model (iMM) | Memory & Identity: tracks objects over time | Temporal Lobe |
| Transition Mixture Model (tMM) | Prediction & Planning: forecasts motion | Frontal Lobe |
| Recurrent Mixture Model (rMM) | Reasoning: links cause to effect | Frontal/Parietal Lobe |

**Performance vs DeepMind DreamerV3:**
- 60% more reliable
- 97% more efficient  
- 39x faster at learning

#### ACT - Action Without Pre-Training
> "ACT allows robots and agents to learn new tasks quickly in physical and digital worlds, **without the extensive pre-training that conventional systems require.**"

Breakthrough result:
> "In August 2025, we published results of our robotics model, which outperformed other models on Meta's Habitat benchmark simulation **without any pre-training**... achieved a 67% success rate, surpassing the previous best alternative of 55%."

> "Unlike a deep-learning robotics model that required imitation-based pre-training with more than 1.3 billion steps to acquire these skills, the VERSES model adapted and learned in real time."

#### SHARE - Multi-Agent Collaboration
Uses **Spatial Web standards** for agent collaboration:
> "Agents using this architecture autonomously reduced building energy use and emissions by 15 to 20 percent... The same framework lets robots share skills instantly and multiple agents cooperate; **what one learns, all can learn.**"

**NASA JPL Application:**
> "In a simulation of the lunar surface, NASA's Jet Propulsion Laboratory applied the Spatial Web standards to coordinate rovers and teams... **When one virtual rover got stuck in a crater, real-time data was sent to the other rovers in a communal gesture, demonstrating how the standards can assist in cooperation.**"

**Key Philosophical Difference:**
Unlike deep learning approaches that require massive pre-training, VERSES uses **active inference** — continuously updating beliefs based on new evidence, similar to how humans learn:
> "A toddler repeatedly dropping a spoon on the ground might be refining their understanding of gravity."

---

## Summary: The Convergence

The world model landscape is converging on a few key principles:

| Principle | Implementation |
|-----------|---------------|
| **Video as Universal Representation** | All approaches use video generation as core mechanism |
| **Scale Pre-training** | Web-scale video, 10k-44k hours of diverse data |
| **Inverse Dynamics** | Separate models convert video predictions to robot actions |
| **Real-Time Inference** | 7-10Hz closed-loop control through distillation/optimization |
| **Zero-Shot Generalization** | Novel tasks, objects, environments without task-specific training |
| **Cross-Embodiment Transfer** | 30 min to adapt to new robots |
| **Retrieval-Augmentation** | Grounding generation in real data (street views, UI states) |
| **Interactive & Controllable** | Real-time user interaction (20-24 FPS in Genie 3) |
| **Imagination Training** | Agents learn inside world models without real environment interaction (Dreamer 4) |
| **Active Inference** | Bayesian belief updating as alternative to neural nets (VERSES) |
| **Spatial Intelligence** | 3D world understanding as next frontier (World Labs) |
| **Memory & Consistency** | Recalling previous states for coherent long-horizon generation |
| **Skill Sharing** | Multi-agent collaboration where learned skills propagate instantly |

### Two Paradigms Emerging

**1. Deep Learning Approach** (NVIDIA, 1X, DeepMind, Rhoda)
- Massive pre-training on video data
- Neural network world models
- Scale is the primary driver
- Examples: DreamDojo, DreamZero, Genie 3, Dreamer 4

**2. Active Inference Approach** (VERSES AI)
- Probabilistic Bayesian models
- Continuous belief updating
- No pre-training required (learns in real-time)
- Interpretable, modular architecture
- Examples: Genius SENSE/THINK/ACT/SHARE

### The Unified Vision

Whether through neural networks or Bayesian inference, the goal is the same:

> **World models that can imagine, predict, and act** — learning from diverse experience to generalize to novel situations.

The future of embodied AI is being built on these foundations:
- **Video** as the densest representation of world dynamics
- **Text** as the most flexible interface (your project)
- **3D** as the spatial foundation (World Labs, VERSES)
- **Imagination** as the training ground (Dreamer 4)
- **Real-time interaction** as the deployment mode (Genie 3)

---

*Compiled: March 2026*  
*Updated with latest research: March 21, 2026*
