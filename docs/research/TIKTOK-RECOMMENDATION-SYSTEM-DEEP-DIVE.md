# TikTok Recommendation System: Deep Research Report

> **Purpose**: Exhaustive technical analysis of TikTok's recommendation system for informing the design of a local, personal behavior model.
> **Date**: 2026-04-06
> **Status**: Research only -- no code changes.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Official Disclosures](#2-official-disclosures)
3. [The Monolith Architecture](#3-the-monolith-architecture)
4. [Signal Collection & Weighting](#4-signal-collection--weighting)
5. [The Leaked "Algo 101" Document](#5-the-leaked-algo-101-document)
6. [Content Understanding](#6-content-understanding)
7. [Interest Graph vs Social Graph](#7-interest-graph-vs-social-graph)
8. [Pipeline Architecture](#8-pipeline-architecture)
9. [Multi-Objective Optimization](#9-multi-objective-optimization)
10. [Exploration vs Exploitation](#10-exploration-vs-exploitation)
11. [Cold Start & Rapid Profiling](#11-cold-start--rapid-profiling)
12. [Temporal Dynamics](#12-temporal-dynamics)
13. [Diversity & Filter Bubble Mitigation](#13-diversity--filter-bubble-mitigation)
14. [Infrastructure at Scale](#14-infrastructure-at-scale)
15. [Reverse Engineering Studies](#15-reverse-engineering-studies)
16. [Academic Research Findings](#16-academic-research-findings)
17. [Key Essays & Analyses](#17-key-essays--analyses)
18. [Lessons for Personal Behavior Modeling](#18-lessons-for-personal-behavior-modeling)
19. [Source Bibliography](#19-source-bibliography)

---

## 1. Executive Summary

TikTok's recommendation system is widely regarded as the most effective content personalization engine ever deployed at consumer scale. It serves over a billion users with sub-150ms latency, learns a new user's preferences in roughly 30-40 minutes, and updates its models in near real-time (minute-level parameter synchronization). The system is built on ByteDance's proprietary **Monolith** framework, which introduced collisionless hash embeddings and online training to the recommendation systems field.

The core innovation is not any single algorithm but the **tight feedback loop** between content consumption, signal capture, model update, and content serving. TikTok's product design (one video at a time, swipe to dismiss) generates unambiguous behavioral signals that train the algorithm with exceptional clarity. As Eugene Wei wrote: *"The magic of TikTok is the tight feedback loop between creation, consumption, and the algorithm -- the user trains the algorithm, and the algorithm trains the user on what to create."*

What makes TikTok's approach relevant to personal behavior modeling: it demonstrates that you can build a highly accurate preference model from **implicit behavioral signals alone**, with **rapid adaptation** to changing interests, using **relatively standard ML techniques** applied with exceptional engineering rigor.

---

## 2. Official Disclosures

### 2.1 The June 2020 Blog Post

TikTok's most detailed public disclosure came in a [June 2020 Newsroom post](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you) explaining the For You feed. Key revelations:

**Ranking factors (confirmed by TikTok):**
- **User interactions**: videos you like or share, accounts you follow, comments you post, and content you create
- **Video information**: captions, sounds, and hashtags
- **Device and account settings**: language preference, country setting, and device type (these receive *"lower weight in the recommendation system relative to other data points"*)

**Signal weighting** (direct quote): *"a strong indicator of interest, such as whether a user finishes watching a longer video from beginning to end, would receive greater weight"*

**What does NOT matter** (direct quote): *"neither follower count nor whether the account has had previous high-performing videos are direct factors in the recommendation system"*

**Diversity mechanism** (direct quote): *"your For You feed generally won't show two videos in a row made with the same sound or by the same creator"*

**Exploration** (direct quote): *"sometimes you may come across a video in your feed that doesn't appear to be relevant to your expressed interests"* -- these are deliberately injected to help users *"stumble upon new content categories, discover new creators"*

Source: [How TikTok recommends videos #ForYou - TikTok Newsroom](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)

### 2.2 Transparency Center

TikTok's [official transparency page](https://www.tiktok.com/transparency/en/recommendation-system) provides less technical detail but confirms:
- The For You feed's goal is *"providing original content that honors our mission of inspiring creativity and bringing joy"*
- *"Our recommendation system is designed with user safety as a primary consideration"*
- Users can *"refresh their For You feed"* if recommendations feel stale, after which *"our recommendation system will then begin to surface more content based on new interactions"*
- Videos by users under 16 are not eligible for FYP recommendation
- Family Pairing allows keyword filters

### 2.3 Content Safeguarding & Diversification (2021)

A [TikTok Newsroom update](https://newsroom.tiktok.com/en-us/an-update-on-our-work-to-safeguard-and-diversify-recommendations) revealed more about their approach to algorithmic harm:

- *"we're testing ways to avoid recommending a series of similar content -- such as around extreme dieting or fitness, sadness, or breakups"*
- *"we're working to recognize if our system may inadvertently be recommending only very limited types of content that, though not violative of our policies, could have a negative effect"*
- They consult *"experts across medicine, clinical psychology, and AI ethics, members of our Content Advisory Council, and our community"*

### 2.4 Content Moderation at Scale (2024 Transparency Report)

- Over 96% of violative content removed through automated technology was taken down before receiving any views
- Over 80% of violative video removals in 2024 were automated
- Automated moderation accuracy rate: 99.1% (H2 2024)
- Detection uses vision-based computer vision models (weapons, hate symbols) and audio-based review

Source: [TikTok Transparency Center](https://www.tiktok.com/transparency/en-us/)

---

## 3. The Monolith Architecture

### 3.1 Overview

ByteDance published the **Monolith** paper in 2022: *"Monolith: Real Time Recommendation System With Collisionless Embedding Table"* (presented at the 5th Workshop on Online Recommender Systems and User Modeling, ORSUM@ACM RecSys 2022). The paper is available at [arxiv.org/abs/2209.07663](https://arxiv.org/abs/2209.07663) and the framework is [open-sourced on GitHub](https://github.com/bytedance/monolith).

The paper's key insight: *"general-purpose frameworks fall short of business demands in recommendation scenarios"* -- so ByteDance built a system that makes *"radically different design choices"* optimized specifically for recommendation.

The paper emphasizes: *"Engineering in recommender systems might be more if not equally important as training a new SOTA model."*

### 3.2 Collisionless Embedding Tables

**The problem**: Recommendation data is mostly categorical and sparse (user IDs, video IDs, hashtag IDs). Standard TensorFlow `tf.Embedding` *"freezes the shape of the matrix throughout the training/serving process"* -- you must pre-allocate for all possible IDs, and hash collisions degrade model quality.

**The solution**: Monolith uses a **Cuckoo Hashmap** -- a data structure maintaining two hash tables (T0, T1) with different hash functions (h0(x), h1(x)):
- When inserting element A into T0 at position h0(A), if the slot is occupied by element B, B gets evicted to T1 using h1(B)
- This cascading continues *"until all elements stabilize, or rehash happens when insertion runs into a cycle"*
- Guarantees O(1) lookup and amortized O(1) insertion
- Implemented as a TensorFlow resource operation

**Performance**: Collisionless tables demonstrated consistent AUC improvements over collision-based tables across both training epochs and daily retraining cycles (tested on Criteo Ads dataset and MovieLens 25M).

### 3.3 Memory Optimization

Two key strategies prevent the embedding table from growing unboundedly:

1. **Frequency Filtering**: *"Filter by a threshold of occurrences before insertion"* with a tunable hyperparameter per model, plus a probabilistic filter. Long-tail IDs with minimal impact on model quality get filtered out.

2. **Expirable Embeddings**: *"Set an expiry time for each ID"* that is *"tunable for each embedding table: different tables will have different sensitivity to historical information."* Less-active users *"underfit due to fewer training examples"* and *"don't affect platform-level metrics so much"* so their embeddings can be retired.

### 3.4 Online Training Architecture

Monolith uses a **Parameter Server (PS)** architecture with two distinct server roles:

- **Training-PS**: Updates model parameters using the real-time event stream. Trains continuously but does NOT serve inference.
- **Inference-PS**: Handles all prediction requests. Periodically syncs its parameters with Training-PS.

**Training flow**:
1. Batch training runs first as an initial checkpoint (single pass over historical data)
2. Online training activates immediately upon batch completion
3. Workers consume real-time user data from a Kafka queue *"on-the-fly"* rather than stored batches
4. Parameters update instantly, syncing to serving infrastructure

### 3.5 Streaming Data Pipeline

The data pipeline architecture:
1. Two **Kafka queues** capture user actions (clicks, likes, shares) and model server features separately
2. An **Apache Flink** joiner combines these streams using unique request keys, with in-memory caching and disk-based KV storage to handle asynchronous arrival timing
3. Joined data transforms into training examples
4. **Negative sampling** corrects class imbalance between positive and negative examples
5. **Log-odds correction during serving** ensures *"the online model is an unbiased estimator"*

### 3.6 Parameter Synchronization

**Selective sync mechanism**: Only IDs updated between sync cycles get synchronized to Inference-PS. This dramatically reduces network bandwidth.

- **Sparse embeddings**: Sync keys whose vectors updated during the last ~1 minute
- **Dense parameters**: Sync frequency is ~1 day (dense layers receive non-zero gradients on every data point, so they change slowly)
- Network estimate: *"~400 MB"* per minute for *"100,000 IDs with 1024 vector size"*

**Sync interval impact** (tested on Criteo Ads):
| Interval | Performance |
|----------|-------------|
| 30 minutes | Best retention of online training gains |
| 1 hour | Moderate degradation |
| 5 hours | Significant degradation |

Real-time training outperformed batch training in ALL tested intervals.

### 3.7 Fault Tolerance

- Training-PS snapshots every 24 hours, balancing *"cost and the drop in model performance"* during recovery
- The authors note *"no loss in model quality"* occurred despite infrequent snapshots
- The system deliberately trades some accuracy for fault tolerance in production

Sources:
- [Monolith Paper (arXiv)](https://arxiv.org/abs/2209.07663)
- [Paper Summary by Dhruvil](https://dhruvil.substack.com/p/paper-summary-monolith-real-time)
- [Paper Review by Shivam Rana](https://shivamrana.me/2022/10/tiktok-monolith-review/)
- [The Secret Sauce of TikTok's Recommendations - Shaped.ai](https://www.shaped.ai/blog/the-secret-sauce-of-tik-toks-recommendations)
- [ByteDance Monolith - Next Platform](https://www.nextplatform.com/2022/09/26/chinas-bytedance-intros-different-approach-to-recommendation-at-scale/)

---

## 4. Signal Collection & Weighting

### 4.1 The Complete Signal Taxonomy

TikTok tracks an extraordinarily rich set of behavioral signals. Based on the leaked "Algo 101" document, official disclosures, and reverse-engineering studies, here is the most complete picture available:

**Positive Engagement Signals (strong to weak):**
| Signal | Type | Estimated Weight | Notes |
|--------|------|-----------------|-------|
| Rewatch/Replay | Passive | Highest (~5 points) | Clearest signal of value |
| Watch to Completion | Passive | Very High (~4 points) | Completion rate is dominant metric |
| Share (to friends/platforms) | Active | High (~3 points) | Shares weighted ~3x higher than likes |
| Comment | Active | Medium (~2 points) | Signals deep engagement |
| Like | Active | Lower (~1 point) | Easiest to fake, lowest signal quality |
| Follow (from video) | Active | Medium-High | Strong persistent interest signal |
| Save/Bookmark | Active | High | Utility/reference signal |
| Pause (to read/absorb) | Passive | Mild positive | *"a pause, even without a like, is a 'tell me more'"* |

**Negative Signals:**
| Signal | Type | Impact |
|--------|------|--------|
| Quick swipe/skip | Passive | Strong negative -- *"a quick flick past a video is a 'no'"* |
| "Not Interested" tap | Active | Explicit negative -- algorithm adjusts after ~20-50 consistent signals |
| Long-press to skip | Active | Moderate negative |
| Drop-off in first seconds | Passive | Very strong negative -- *"a high skip rate early in a video's life can kill it"* |
| Scroll speed | Passive | *"Your scroll speed is a silent conversation with the algorithm"* |

**Critical insight**: *"Explicit actions carry less weight than passive behavior because passive behavior is harder to fake -- you can't fake watching something twice."*

### 4.2 Watch Time Measurement Precision

Watch time is measured with sub-second granularity. The algorithm tracks:
- **Absolute watch time**: Total seconds viewed
- **Completion rate**: Percentage of video watched (the dominant signal)
- **Loop count**: How many times the video replayed
- **Abandon point**: Exactly where the user stopped watching
- **Dwell time**: Time lingering on a post before scrolling

The WSJ investigation found that even pausing on a video (without any explicit interaction) was logged as a signal of interest.

### 4.3 The Leaked Point System

Multiple sources reference a simplified engagement weighting:
- Rewatch: **5 points**
- Watch to Completion: **4 points**
- Share: **3 points**
- Comment: **2 points**
- Like: **1 point**

This is described as a simplified heuristic. The actual system uses continuous predicted probabilities, not discrete point values.

Sources:
- [Nobody Tells You What's Actually Inside TikTok's Algorithm - BuildWithAWS](https://buildwithaws.substack.com/p/most-engineers-miss-whats-really)
- [TikTok Algorithm Guide - Buffer](https://buffer.com/resources/tiktok-algorithm/)
- [How TikTok Uses ML to Keep You Scrolling - BrainForge](https://www.brainforge.ai/blog/how-tiktok-uses-machine-learning-to-keep-you-scrolling)
- [TikTok Algorithm Explained - Kamrun Nahar](https://iknahar.medium.com/how-tiktok-recommendation-algorithm-works-complete-guide-0c02479be44f)

---

## 5. The Leaked "Algo 101" Document

### 5.1 Background

In December 2021, the **New York Times** (reporter Ben Smith) obtained an internal TikTok document titled **"TikTok Algo 101"**, produced by TikTok's Beijing-based engineering team for nontechnical colleagues. A TikTok spokeswoman, Hilary McQuaide, confirmed its authenticity.

### 5.2 The Core Formula

The document revealed the ranking formula:

```
Score = Plike x Vlike + Pcomment x Vcomment + Eplaytime x Vplaytime + Pplay x Vplay
```

The document states this formula is *"highly simplified"* and *"the actual equation in use is much more complicated, but the logic behind [it] is the same."*

**Variable definitions:**
- **P** (Predicted) = Machine learning model's predicted probability that a user will perform an action (like, comment, play)
- **E** (Estimated) = Model's estimated value for a continuous variable (playtime duration)
- **V** (Value) = Business-defined weight for how much the platform values each action type

The formula *"compute[s] an estimated value of showing the video to the user."* Videos are scored, ranked, and the highest-scoring videos are served.

### 5.3 Optimization Objectives

The document revealed the algorithm optimizes for two closely related metrics:
1. **Retention**: Whether a user comes back
2. **Time spent**: Keeping users engaged as long as possible

The document describes the company's *"ultimate goal"* as **adding daily active users**.

### 5.4 Four Macro Objectives

The algorithm balances four high-level objectives:
1. **User value**: Immediate satisfaction from recommendations
2. **Long-term user value**: Whether the user returns tomorrow/next week
3. **Creator value**: Fair exposure and incentive for content creators
4. **Platform value**: Revenue, growth, and ecosystem health

### 5.5 Boosting and Penalty Mechanisms

The leaked doc revealed specific strategies:
- **Boost**: Videos by producers whose works a user watched previously (recency/familiarity signal)
- **Penalty**: Videos in categories the user watched earlier the same day (anti-fatigue/anti-rabbit-hole)
- **Penalty**: Videos that explicitly ask viewers to like them (spam/engagement-bait suppression)

### 5.6 Expert Assessment

Notably, a computer science professor quoted by the NYT observed: *"There seems to be some perception (by the media? or the public?) that they've cracked some magic code for recommendation, but most of what I've seen seems pretty normal."*

This is an important finding: **TikTok's advantage is not algorithmic novelty but engineering execution** -- the tight feedback loop, real-time training, and product design that generates clear signals.

Sources:
- [Leaked Info Reveals How TikTok's Algorithm Works - DeepLearning.ai](https://www.deeplearning.ai/the-batch/what-makes-tiktok-tick/)
- [Leaked TikTok Doc - Gizmodo](https://gizmodo.com/leaked-tiktok-doc-reveals-its-obvious-secret-to-an-addi-1848166901)
- [TikTok's Secret Algorithm Unveils - TechTimes](https://www.techtimes.com/articles/269024/20211206/tiktok-algo-101-leaked-document-tiktok-secret-algorithm-tiktok.htm)
- [NYT Column by Ben Smith](https://bensmith.ghost.io/nyt-column-how-tiktok-keeps-you-watching/)

---

## 6. Content Understanding

TikTok employs a sophisticated **multimodal content analysis** pipeline to understand video content without relying solely on user-provided metadata.

### 6.1 Computer Vision

- Deep learning neural networks trained on *"millions of labeled images"* to recognize traits and characteristics
- Analyzes *"facial features, products, and other traits in people and objects"*
- Evaluates video quality attributes: resolution, aspect ratio, visual complexity
- Uses pre-trained CNNs (ResNet family) for frame-level embedding extraction

### 6.2 Audio Analysis

- NLP algorithms *"transcribe and understand the audio of the videos (whether spoken dialogue or song lyrics)"*
- Identifies keywords and conversation topics
- Sound/music identification for trending audio matching
- Mel-frequency cepstral coefficients (MFCCs) for audio feature extraction

### 6.3 Text and Metadata

- On-screen text extraction via OCR
- Caption analysis using NLP
- Hashtag categorization -- both explicit (user-chosen) and inferred
- TF-IDF and Word2Vec for textual embedding

### 6.4 Hierarchical Content Classification

ByteDance's content understanding system (originally documented for Toutiao/Douyin) uses:
- **Semantic tagged features**: Human-defined classification tags
- **Implicit semantic features**: Auto-extracted topics and keywords
- **Hierarchical taxonomy**: Categories to subcategories structure
- **Entity recognition**: Via *"semantic segmentations and part-of-speech tagging"*

Classification requires *"complete coverage...with low precision requirements"* while entity recognition prioritizes *"high precision."*

### 6.5 Content Safety Models

- Pornography detection: *"ResNet model...99% recall"* on tens of millions of training images
- Vulgar content: Deep neural network model with *"precision of 80%+ and recall of 90%+"*
- Low-quality content detection: *"Recall is now around 95%"* supplemented by human review

Sources:
- [How TikTok Uses Machine Learning - Dev.to/Mage AI](https://dev.to/mage_ai/how-does-tiktok-use-machine-learning-5b7i)
- [How TikTok Wins the RecSys War - Lee Han Chung](https://leehanchung.github.io/blogs/2020/02/18/Tik-Tok-Algorithm/)
- [TikTok Algorithm Ultimate Guide - Beatstorapon](https://beatstorapon.com/blog/tiktok-algorithm-the-ultimate-guide/)

---

## 7. Interest Graph vs Social Graph

### 7.1 The Fundamental Paradigm Shift

TikTok's most radical design decision is building on an **interest graph** rather than a **social graph**. This is the single most important architectural distinction from Facebook, Instagram, and Twitter.

**Social graph** (Facebook model): You see content from people you know. Interest is inferred from social connections. *"Meta will serve you $TOPIC because you have $INTERACTED with $PEOPLE who post $TOPIC."*

**Interest graph** (TikTok model): You see content matching your inferred interests, regardless of who created it. *"TikTok will serve you $TOPIC because you have $INTERACTED with $TOPIC historically."*

### 7.2 Eugene Wei's Analysis

In his landmark essay, Wei identified the key insight:

> *"Using a social graph as a way to reverse engineer the interest graph has always been a roundabout way of building it."*

TikTok's algorithm *"abstracts away culture"* -- it uses machine learning to figure out preferences without needing to understand the content itself. This enabled ByteDance to penetrate Western markets despite engineers who *"don't understand most U.S. TikTok memes."*

### 7.3 Why Interest Graphs Win

1. **Every swipe is a clear data point**: A definitive "yes" or "no" providing immediate, high-quality feedback
2. **No cold start dependency on friends**: You don't need to build a social network before getting value
3. **Meritocratic content distribution**: *"a creator with zero followers can go viral overnight"*
4. **Commercial value**: *"The interest graph is where almost all the money is -- for targeted advertising, for e-commerce, for SVOD subscriptions."*

### 7.4 Algorithm-Friendly Product Design

The a16z "Seeing Like an Algorithm" thesis identifies TikTok's key product design choice: presenting one video at a time forces unambiguous signal generation. Unlike a scrolling feed where *"the algorithm has no idea which item your eyes are actually looking at,"* TikTok's full-screen format isolates variables so the algorithm can understand precisely what you're paying attention to.

### 7.5 Industry Impact

Instagram, Facebook, YouTube, and LinkedIn have all shifted toward interest-graph-based recommendation since TikTok's rise, with Instagram Reels and YouTube Shorts being direct responses.

Sources:
- [TikTok and the Sorting Hat - Eugene Wei](https://eugenewei.substack.com/p/tiktok-and-the-sorting-hat)
- [TikTok and the Sorting Hat - Eugene Wei's Blog](https://www.eugenewei.com/blog/2020/8/3/tiktok-and-the-sorting-hat)
- [Interest Graph vs Social Graph - The Shelf](https://www.theshelf.com/the-blog/social-media-algorithms-interest-graph-vs-social-graph/)
- [How TikTok's Content Graph is Reshaping Social Platforms - Culturix](https://www.culturix.ca/blog/tiktok-content-graph-reshaping-social-platforms)
- [16 Minutes on TikTok and Seeing Like an Algorithm - a16z](https://a16z.com/podcast/16-minutes-on-the-news-41-tiktok-and-seeing-like-an-algorithm/)

---

## 8. Pipeline Architecture

### 8.1 High-Level Pipeline

TikTok's recommendation system follows the standard industrial multi-stage pipeline, but with distinctive engineering choices at each stage:

```
All Videos (100s of millions)
    |
    v
[1. Candidate Generation / Retrieval] --> ~100-1000 candidates
    |
    v
[2. Pre-Ranking / Coarse Ranking] --> ~100 candidates
    |
    v
[3. Fine Ranking] --> ~50 candidates
    |
    v
[4. Re-Ranking / Post-Processing] --> ~30 items
    |
    v
[5. Serving / Delivery] --> User's For You feed
```

**Latency budget**: The entire pipeline must execute within **50ms inference** to maintain real-time responsiveness. Some sources cite sub-150ms end-to-end including network latency.

### 8.2 Stage 1: Candidate Generation (Retrieval)

Reduces hundreds of millions of videos to ~100-1000 candidates per request.

**Deep Retrieval Model** (published by ByteDance: [arxiv.org/abs/2007.07203](https://arxiv.org/abs/2007.07203)):
- Uses a matrix abstraction with D columns and K nodes per column
- Each video is indexed by one or more paths through this matrix
- Path probability computed via chain rule: `p(c1, c2, ..., cD|user) = product of p(ca|user, c1, ..., ca-1)`
- Each column is represented by *"a multi-layer perceptron followed by K softmax functions"*
- **Beam search** inference with beam size ~100K returns candidate videos
- Time complexity: O(DKB log B), sub-linear in total item count
- Trained with **Expectation-Maximization**: expectation step backpropagates loss, maximization step finds optimal path mappings
- Collision penalty: `Qpen = Q - alpha * sum(|c|^4 / 4)` where |c| represents items per path

**Multiple retrieval channels** run in parallel:
- Interest clusters / topic similarity
- Sound/audio trends
- Location-based relevance
- Taste graph connections (users with similar behavior)
- Freshness (new content injection)

**Two-Tower Architecture** (for some retrieval channels):
- User tower: computes user embedding online in real-time
- Item tower: item embeddings precomputed offline, stored in ANN index
- ByteDance uses ALBERT and Vision Transformer twin-tower architecture for text/image
- Approximate nearest neighbor search via FAISS or HNSW for efficient retrieval

### 8.3 Stage 2: Pre-Ranking

A lightweight model (often logistic regression) provides fast scoring to narrow candidates further. Uses *"a simple model with a softmax output function"* for low-latency inference to rank multiple items sharing the same retrieval path.

### 8.4 Stage 3: Fine Ranking

The core ranking stage uses **Multi-Task Learning (MTL)** to simultaneously predict:
- Probability of like (P_like)
- Probability of comment (P_comment)
- Probability of share (P_share)
- Probability of follow (P_follow)
- Estimated watch time (E_playtime)

**Model architectures explored:**
- **MMoE (Multi-gate Mixture-of-Experts)**: Shared expert submodels across all tasks with per-task gating networks. *"By far the most widely adopted"* in web-scale ranking systems (originally from Google, KDD 2018).
- **PLE (Progressive Layered Extraction)**: Separates shared and task-specific components with progressive routing. Won best paper at RecSys 2020.

**Final score computation:**
```
Score = sum(P_task x V_task)
```
Where P_task is predicted probability/estimated value and V_task is the business-defined weight for each task.

### 8.5 Stage 4: Re-Ranking / Post-Processing

After scoring, additional constraints and business rules are applied:
- **Diversity enforcement**: No two consecutive videos from the same creator or with the same sound
- **Similarity check**: Replaces similar content to ensure feed variety
- **Same-day category penalties**: Penalizes categories the user already consumed heavily that day
- **Safety filtering**: Content with mature themes restricted from users under 18
- **Regional rules**: Ensures creators from users' regions get exposure
- **Anti-spam**: Penalizes videos that explicitly ask for likes
- **Engagement-bait suppression**: Down-ranks manipulative content

### 8.6 Stage 5: Serving

- Multi-layer caching network using **Redis**, **Aerospike**, and **ByteEdge CDN**
- Trending videos preloaded near demand zones
- Sub-150ms end-to-end latency target
- **Cassandra** for NoSQL storage, **Apache Spark** for batch processing

Sources:
- [Deep Dive: TikTok Recommender System - The AI Edge Newsletter](https://newsletter.theaiedge.io/p/deep-dive-how-to-build-the-tiktok)
- [Deep Retrieval Paper (arXiv)](https://arxiv.org/abs/2007.07203)
- [TikTok System Design - TechAhead](https://www.techaheadcorp.com/blog/decoding-tiktok-system-design-architecture/)
- [Two-Tower Model Deep Dive - Shaped.ai](https://www.shaped.ai/blog/the-two-tower-model-for-recommendation-systems-a-deep-dive)

---

## 9. Multi-Objective Optimization

### 9.1 The Multi-Objective Function

TikTok's ranking model does NOT optimize for a single metric. The final ranking score combines multiple predicted outcomes:

```
Score = sum_over_tasks(P_task x V_task)
```

Where:
- P_task = predicted probability for engagement tasks (like, comment) or estimated value for regression tasks (watch time)
- V_task = business weight assigned to each task, tuned by product teams

### 9.2 Competing Objectives

TikTok balances at least these objectives simultaneously:

1. **Short-term engagement**: Watch time, likes, comments, shares (immediate satisfaction)
2. **Long-term retention**: Will the user come back tomorrow? Next week? (sustainable engagement)
3. **Creator fairness**: Equitable exposure for diverse creators, not just viral ones
4. **Content diversity**: Preventing monotonous feeds that lead to boredom
5. **User safety**: Filtering harmful or policy-violating content
6. **Platform growth**: Adding daily active users (the "ultimate goal" per leaked docs)
7. **Revenue**: Ad placement effectiveness and advertiser satisfaction

### 9.3 The Seesaw Phenomenon

Multi-task learning in recommendations suffers from a well-documented problem: improving one task often degrades another. The PLE paper (RecSys 2020) identified this as the *"seesaw phenomenon"* where *"performance of one task is often improved by hurting the performance of some other tasks."*

MMoE addresses this by allowing different tasks to weight shared experts differently through per-task gating networks.

### 9.4 Engagement Constraints

TikTok is reportedly NOT purely maximizing engagement. The system manages the tradeoff between:
- **Viral content** (short-term engagement spikes)
- **Niche, satisfying content** (long-term user retention)

The leaked document's same-day category penalty is one concrete example: even if the model predicts you'd watch another cooking video, it may deliberately down-rank it to prevent fatigue.

Sources:
- [TikTok Algorithm Ultimate Guide - Beatstorapon](https://beatstorapon.com/blog/tiktok-algorithm-the-ultimate-guide/)
- [Secret Sauce Behind TikTok's Algorithm - God of Prompt](https://www.godofprompt.ai/blog/the-secret-sauce-behind-tiktoks-addictive-algorithm)
- [Multi-Task Learning in RecSys - ML Frontiers](https://mlfrontiers.substack.com/p/multi-task-learning-in-recommender)

---

## 10. Exploration vs Exploitation

### 10.1 The Core Tradeoff

Every recommendation system must balance:
- **Exploitation**: Showing content the system is confident the user will enjoy (maximizes immediate engagement)
- **Exploration**: Showing novel content to discover new interests and prevent staleness (maximizes long-term engagement and information gain)

### 10.2 TikTok's Approach

TikTok uses **contextual bandits** to balance exploration and exploitation. The framework provides *"a framework for balancing exploitation (showing a user a video the system is confident they will like) with exploration (showing a user a novel video to gather more data and prevent the feed from becoming stale)."*

**Concrete mechanisms:**
- Periodically introduces videos from *"adjacent or entirely new categories to test the user's interest and potentially expand their taste profile"*
- Multi-armed bandit algorithms inject random exploration videos
- Epsilon-greedy approaches with exploration parameter ~0.1 (10% exploration in reference implementations)

### 10.3 Academic Measurement (WebConf 2024)

The landmark Vombatkere et al. paper from the University of Washington quantified TikTok's exploration/exploitation ratio using real user data:

**Key findings:**
- TikTok **exploits** user interests in **30% to 50%** of recommended videos in the first 1,000 videos
- Real TikTok users show **50%+ mean exploit fraction** vs 31% for bots and 20% for randomized baselines
- **Exploit videos** average a personalization score of **0.83** (highly targeted)
- **Explore videos** average just **0.08** (widely shown to many users)
- Exploitation rates increase *"steadily for the first few videos"* then stabilize around video 100+

This means roughly **50% of your feed is exploration** -- content TikTok is testing to learn about you or broaden your interests. This is a remarkably high exploration rate compared to most recommendation systems.

### 10.4 The Local Optima Problem

A practical observation from Hacker News engineers: recommendation systems are *"really good at finding local optima quickly, and then are rather bad at getting out of them once they get there."* TikTok's high exploration rate and feed refresh feature are defenses against this.

Sources:
- [TikTok and the Art of Personalization (WebConf 2024)](https://arxiv.org/html/2403.12410v1)
- [Exploration vs Exploitation in RecSys - Shaped.ai](https://www.shaped.ai/blog/explore-vs-exploit)
- [Monolith HN Discussion](https://news.ycombinator.com/item?id=35573624)

---

## 11. Cold Start & Rapid Profiling

### 11.1 The "40 Minutes" Claim

The Wall Street Journal's investigation demonstrated that TikTok can profile a new user in as little as **36 minutes**. In their test, a bot programmed to linger on sad content (without ever liking it) received a feed that was **93% depression-related** after just 36 minutes of usage.

More broadly, TikTok can *"build a reasonably accurate preference model for a brand new user in about 30 to 40 minutes of usage"* with some estimates suggesting it takes as few as **200 interactions**.

### 11.2 Cold Start Strategy

**Phase 1: Zero data (first few videos)**
- Interest category selection during onboarding (pets, travel, sports, etc.)
- If skipped, user receives *"a generalized feed of popular videos"*
- **Demographic bucketing**: Initial recommendations use demographic clustering, presenting content popular within cohorts sharing age, location, and inferred interests

**Phase 2: Early signals (first session)**
- The feed initially relies on **location and language settings**
- After first interactions, *"views, full watch-throughs, skips, likes, comments, and follows begin to matter more"*
- Following and liking are the **primary drivers** of rapid personalization

**Phase 3: Rapid convergence (~100 videos)**
- Exploitation rates increase steadily for the first ~100 videos then stabilize
- By this point, the system has a working preference model

### 11.3 Session-Based Sequential Modeling

TikTok uses sequence models (likely GRU-based RNNs or Transformers) to predict in-session intent:
- *"RNNs look at the strict chronological sequence of user actions and use that sequential memory to predict the next action"*
- Latency requirement: *"when a user swipes, the RNN must update its state and fetch the next video in under 50 milliseconds"*
- The system predicts the *"immediate future based on the immediate past"* rather than relying solely on lifetime history

### 11.4 HLLM: Next-Generation Cold Start (2024)

ByteDance published **HLLM (Hierarchical Large Language Model)** in September 2024, specifically targeting cold start:
- Two-component architecture: **Item LLM** (extracts features from item descriptions) + **User LLM** (models user behavior from item embeddings)
- Reduces computational complexity by decoupling item and user modeling
- *"Significantly outperforming traditional ID-based models in cold-start scenarios"*
- R@5 of 6.129 vs SASRec's 5.142; R@10 of 12.475 vs SASRec's 11.010
- Scales to 7B parameters

Source: [ByteDance HLLM (GitHub)](https://github.com/bytedance/HLLM)

Sources:
- [WSJ TikTok Algorithm Investigation](https://www.tabcut.com/blog/post/How-TikTok-s-Algorithm-Figures-You-Out-WSJ)
- [How Session-Based RNNs Predict Your Next Swipe - TechnoManagers](https://www.technomanagers.com/p/how-session-based-rnns-predict-your)
- [HLLM Paper - MarkTechPost](https://www.marktechpost.com/2024/09/20/bytedance-introduced-hierarchical-large-language-model-hllm-architecture-to-transform-sequential-recommendations-overcoming-cold-start-challenges-and-enhancing-scalability-with-state-of-the-art-pe/)

---

## 12. Temporal Dynamics

### 12.1 Session-Level vs Long-Term Preferences

TikTok models user interest at multiple time scales:

**Micro-level (within session)**:
- Sequential models (GRU/Transformer) capture current session intent
- *"By the time you're three seconds into a video, the system is already scoring candidates for what comes next"*
- Multi-armed bandits *"intentionally break the sequence to test for new intents"*

**Meso-level (across sessions)**:
- Same-day category penalties prevent within-day topic saturation
- The leaked document mentions penalizing *"videos in categories that the user watched earlier the same day"*

**Macro-level (long-term)**:
- Interest evolution tracked through embedding drift
- Expirable embeddings in Monolith automatically retire stale user interests
- ByteDance's Large Memory Network (LMN) can *"temporally memorize user long-term interest through a user-aware block"*

### 12.2 Interest Decay Mechanisms

ByteDance's system implements multiple decay strategies:
- **Time decay**: Discounts older interactions with exponential decay `weight = e^(-lambda * (t_current - t_i))`
- **Noise filtering**: Removes clickbait-driven interactions
- **Discounting top news**: Reduces the signal from trending content that attracted engagement through virality rather than genuine interest
- **Staleness-based embedding expiry**: Each embedding table has *"different sensitivity to historical information"*

### 12.3 Real-Time Adaptation

The Monolith online training architecture enables **minute-level model updates**:
- Sparse embedding updates sync every ~1 minute
- *"This enables the model to interactively adapt itself according to a user's feedback in real time"*
- The system *"captures the latest hotspots and helps users discover new interests rapidly"*

### 12.4 Temporal Feature Encoding

Contextual features include temporal signals encoded via:
- Sine/cosine transforms of timestamps (cyclical encoding for time-of-day, day-of-week)
- Device type and network speed as proxies for context (mobile on WiFi = at home, mobile on cellular = commuting)
- Session duration as a fatigue indicator

Sources:
- [ByteDance's Recommendation System (Lee Han Chung)](https://leehanchung.github.io/blogs/2020/02/18/Tik-Tok-Algorithm/)
- [Large Memory Network for Recommendation](https://arxiv.org/html/2502.05558v3)
- [ByteDance Monolith Notes - Raghav Bali](https://medium.com/@Rghv_Bali/notes-on-bytedance-monolith-623e3a276f9e)

---

## 13. Diversity & Filter Bubble Mitigation

### 13.1 Confirmed Diversity Mechanisms

**Consecutive de-duplication** (confirmed by TikTok):
- *"our systems won't recommend two videos in a row made by the same creator or with the same sound"*
- Enriches viewing experience and promotes exposure to diverse perspectives

**Similarity check** (final stage):
- Before serving, the system *"replaces similar content to make sure your feed has variety"*

**Category saturation penalties** (from leaked doc):
- Same-day penalty for over-consumed categories
- Prevents rabbit-hole deepening within a single session

**Intentional exploration injection**:
- TikTok deliberately introduces videos *"from adjacent or entirely new categories to test the user's interest"*
- These create *"moments of unexpected discovery that enhance long-term retention"*

### 13.2 Safeguarding Against Harmful Rabbit Holes

TikTok has acknowledged the risk of algorithmic narrowing:
- *"we're testing ways to avoid recommending a series of similar content -- such as around extreme dieting or fitness, sadness, or breakups"*
- Individual videos may be policy-compliant but harmful in aggregate
- Work involves *"ongoing conversations with experts across medicine, clinical psychology, and AI ethics"*

### 13.3 User Controls

- **"Not Interested"** button: Explicit negative feedback for content types
- **Content filtering**: Users can choose words or hashtags to exclude from FYP
- **Feed refresh**: Users can reset their FYP entirely and retrain from scratch
- **Family Pairing**: Parental keyword filters

### 13.4 Limitations

Despite these mechanisms, research shows TikTok still creates significant filter bubbles. The WSJ investigation found bots were *"driven into rabbit holes that contained concerning content"* -- one bot with a general interest in politics ended up receiving election fraud and QAnon conspiracy content.

Sources:
- [TikTok Recommendation Diversity Update](https://newsroom.tiktok.com/en-us/an-update-on-our-work-to-safeguard-and-diversify-recommendations)
- [WSJ TikTok Investigation](https://awards.journalists.org/entries/inside-tiktoks-dangerously-addictive-algorithm/)

---

## 14. Infrastructure at Scale

### 14.1 Data Processing Stack

| Component | Technology | Role |
|-----------|-----------|------|
| Event streaming | Apache Kafka | Logs user actions (millions of events/minute) |
| Stream processing | Apache Flink | Joins event streams, creates training examples |
| Batch processing | Apache Spark / Hadoop | Historical data processing |
| Online training | Monolith (custom TF) | Real-time parameter updates |
| Feature store | Custom + Redis/DynamoDB | Feature serving for training and inference |
| Embedding storage | Cuckoo Hashmap (custom) | Collisionless embedding tables |
| Caching | Redis, Aerospike | Low-latency feature lookups |
| CDN | ByteEdge CDN | Video delivery near demand zones |
| NoSQL | Cassandra | Persistent storage |
| Graph database | ByteGraph | User-item relationship graphs |
| Data warehouse | Magnus (Apache Iceberg) | 5+ EB scale, 10K-column wide tables |

### 14.2 Magnus Data Management System (VLDB 2025)

ByteDance's **Magnus** system, built on Apache Iceberg, manages the data layer:
- Deployed for over **5 years** at ByteDance
- Data size exceeds **5 exabytes**
- Used across search, advertising, recommendation, and large models
- **Krypton format**: Reduces storage by 30% vs Parquet for 10,000-column tables, reduces footer parsing by 80%
- Git-like branching and tagging for metadata
- Native support for Large Recommendation Models (LRM) training workloads

### 14.3 Scale Metrics

- **Tens of billions** of raw feature vectors
- **Billions** of feature vectors across **tens of thousands** of video types
- Model serves **over 1 billion users** globally
- **Sub-150ms** end-to-end latency (including network)
- **50ms** inference budget for the core pipeline
- Sparse embedding sync: **~400 MB/minute** for 100K IDs at 1024 dimensions

### 14.4 A/B Testing Platform

ByteDance operates a sophisticated experimentation system:
- *"Splits users into buckets offline, then distribute traffics to different experiments online"*
- Example: *"10% traffic with two experimental groups each having 5% of traffic"*
- Data collected *"in quasi real time"* with hourly observation
- Typically *"analyzed on a daily basis"*
- Human oversight remains essential: *"Many improvements still require manual analysis, and major improvements require manual evaluation"*

Sources:
- [Magnus Paper (VLDB 2025)](https://dl.acm.org/doi/10.14778/3750601.3750620)
- [ByteGraph Paper](https://vldb.org/pvldb/vol15/p3306-li.pdf)
- [ByteDance Recommendation System Overview](https://leehanchung.github.io/blogs/2020/02/18/Tik-Tok-Algorithm/)

---

## 15. Reverse Engineering Studies

### 15.1 The Wall Street Journal Investigation (2021)

**Methodology:**
- Created over **100 automated TikTok accounts** (bots)
- Each bot was programmed with specific interests (extreme sports, dance, astrology, pets)
- Bots expressed interest by **re-watching or pausing** on videos with related hashtags (without using "like")
- Over several months, bots watched **hundreds of thousands of videos**
- Videos were downloaded, classified through *"a mix of machine learning and human labeling"*

**Key findings:**
- The algorithm understood interests in less than **2 hours**, sometimes in as little as **40 minutes**
- One bot programmed for sad content: after **36 minutes**, **93% of its feed** was depression-related
- Bots were driven into rabbit holes -- a politics-interested bot received QAnon conspiracy content
- Over **1,000 videos** were removed from TikTok after the Journal flagged them
- TikTok said it would adjust its algorithm to avoid *"showing users too much of the same content"*

Source: [Inside TikTok's Dangerously Addictive Algorithm - Online Journalism Awards](https://awards.journalists.org/entries/inside-tiktoks-dangerously-addictive-algorithm/)

### 15.2 Hacker News Engineering Community Observations

Key insights from engineers discussing TikTok's system:

**On signal design:**
> *"TikTok gets a definite thumbs up or thumbs down for every video it shows you whereas if you click on one particular sidebar video YouTube can make no conclusion"*

**On feature foundation:**
> *"Their algorithm is really built around their features. Specifically, temporal representations of user interest"*

**On interaction granularity:**
> *"It's not just 'did you click the like button'. It's 'did you swipe it away? How long did you watch...'"*

**On the local optima problem:**
> *"recommendation systems are really good at finding local optima quickly, and then are rather bad at getting out of them once they get there"*

**Important caveat**: The open-sourced Monolith framework is infrastructure/framework only -- *"not ByteDance's actual production recommendation engine."*

Sources:
- [Monolith HN Discussion](https://news.ycombinator.com/item?id=35573624)
- [ByteDance's Recommendation System HN Discussion](https://news.ycombinator.com/item?id=42468362)

---

## 16. Academic Research Findings

### 16.1 "TikTok and the Art of Personalization" (WebConf 2024)

**Authors**: Vombatkere, Mousavi, Zannettou, Roesner, Gummadi
**Published**: ACM Web Conference 2024

**Data**: 347 TikTok users donated their data (GDPR right of access), yielding **4.9M videos** viewed **9.2M times** with **4.1M videos** having complete metadata.

**Framework**: Developed a methodology to classify each recommendation as "exploit" (personalized) or "explore" (novel testing), using:
- **Local features**: Hashtag matches in temporal windows (previous 50 videos)
- **Global features**: Macroscopic patterns across entire viewing history

**Key quantitative results:**

| Metric | Value |
|--------|-------|
| Exploitation rate (real users) | 50%+ mean |
| Exploitation rate (bots) | 31% mean |
| Exploitation rate (random baseline) | 20% |
| Exploit video personalization score | 0.83 (highly targeted) |
| Explore video personalization score | 0.08 (broadly distributed) |

**Personalization drivers** (statistical significance):

| Factor | Impact | p-value |
|--------|--------|---------|
| Following creators | Highest | 10^-14 |
| Liking videos | High | 10^-5 |
| Watch percentage | Medium | 0.03 |
| Early skip rate | Low | 0.14 |

**Critical insight**: Users in the high-exploitation group followed creators for **30%** of videos vs. **2%** in the low-exploitation group. Following is the single strongest personalization driver.

Source: [TikTok and the Art of Personalization (arXiv)](https://arxiv.org/html/2403.12410v1)

### 16.2 CHI 2024: Data Donation Study

**Published**: CHI Conference on Human Factors in Computing Systems, 2024

Key finding: In the first 1,000 videos shown to users, **one-third to one-half** were shown based on TikTok's predictions of user preferences, consistent with the WebConf 2024 findings.

Source: [Analyzing User Engagement with TikTok's Short Format Video Recommendations - ACM](https://dl.acm.org/doi/10.1145/3613904.3642433)

### 16.3 CHI 2025: Controlling Unwanted Content

**Published**: CHI 2025

An audit study found that *"a significant number of explanations provided by TikTok are illogical"* -- TikTok's stated reasons for recommending content often don't match the actual algorithmic behavior.

Source: ["They've Over-Emphasized That One Search" - arXiv](https://arxiv.org/html/2504.13895v1)

### 16.4 MIT Technology Review Commentary (2021)

The ScienceDirect paper analyzing TikTok's recommendation algorithms noted that what sets TikTok apart is not algorithmic novelty but *"the carefully designed consumption flow and the product decisions the company made to favor small creators and avoid content repetitiveness -- as well as the enormous volumes of data at their disposal."*

Source: [A commentary of TikTok recommendation algorithms - ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2667325821002235)

---

## 17. Key Essays & Analyses

### 17.1 Eugene Wei: "TikTok and the Sorting Hat" (August 2020)

The most influential essay on TikTok's algorithm. Key insights:

> *"Machine learning figures out who will like what videos, you don't have to even understand what the videos are about."*

> *"TikTok's algorithm: it abstracts away culture!"*

> *"The interest graph is where almost all the money is -- for targeted advertising, for e-commerce, for SVOD subscriptions."*

> *"An algorithmically driven video-based attack that doesn't try to beat them by being them but by attacking from an oblique angle."*

Wei argues TikTok's approach represents a paradigm shift: instead of building social connections first and inferring interests second (Facebook's model), TikTok builds the interest graph directly through behavioral observation.

Sources:
- [TikTok and the Sorting Hat - Substack](https://eugenewei.substack.com/p/tiktok-and-the-sorting-hat)
- [TikTok and the Sorting Hat - Blog](https://www.eugenewei.com/blog/2020/8/3/tiktok-and-the-sorting-hat)

### 17.2 DeepLearning.ai Analysis

Andrew Ng's team summarized the leaked document findings, noting:
- The formula *"compute[s] an estimated value of showing the video to the user"*
- The algorithm achieved rapid personalization: *"TikTok homed in on most of the bots' interests in less than two hours"*
- **WSJ's primary signals**: Time spent watching, repeat viewings, and whether the video was paused

Source: [Leaked Info Reveals How TikTok's Algorithm Works - DeepLearning.ai](https://www.deeplearning.ai/the-batch/what-makes-tiktok-tick/)

### 17.3 a16z "Seeing Like an Algorithm"

Andreessen Horowitz's analysis focused on algorithm-friendly product design:
- TikTok's full-screen, one-at-a-time format creates unambiguous signals
- Unlike a scrolling feed where the algorithm can't tell what you're looking at
- This product decision is as important as the ML -- it generates cleaner training data

Source: [Tiktok and "Seeing Like an Algorithm" - a16z](https://a16z.com/podcast/16-minutes-on-the-news-41-tiktok-and-seeing-like-an-algorithm/)

---

## 18. Lessons for Personal Behavior Modeling

### 18.1 What Transfers Directly

TikTok's approach contains several principles directly applicable to a local, personal behavior model:

**1. Implicit signals are more reliable than explicit ones.**
TikTok's key insight: *"Explicit actions carry less weight than passive behavior because passive behavior is harder to fake."* For a personal behavior model, **dwell time, context switches, and session patterns** are more informative than self-reported preferences.

**Mapping to personal productivity:**
| TikTok Signal | Personal Behavior Analog |
|---------------|--------------------------|
| Watch completion rate | Task completion rate |
| Dwell time on video | Time spent in app/document/activity |
| Replay/rewatch | Returning to same task repeatedly |
| Quick skip | Rapid context-switch away from activity |
| Share | Choosing to share/save/reference output |
| Like | Explicit rating (less reliable) |
| Time-of-day context | Circadian productivity patterns |
| Session duration | Focus duration / flow state detection |
| Scroll speed | App-switching velocity |

**2. The tight feedback loop matters more than model sophistication.**
A computer science professor reviewing TikTok's leaked algorithm noted: *"most of what I've seen seems pretty normal."* The magic is the **speed of the loop** (observe -> update -> serve -> observe), not algorithmic novelty. For a personal model, even simple models updated frequently will outperform complex models updated infrequently.

**3. Multi-signal fusion beats single-metric optimization.**
TikTok's formula combines multiple predicted behaviors into a single score. A personal behavior model should similarly combine multiple signals (focus time + output quality + energy level + context) rather than optimizing for any single metric.

**4. Temporal decay is essential.**
TikTok uses exponential decay on historical interests: `weight = e^(-lambda * (t_current - t_i))`. A personal model needs the same -- your productivity patterns from 6 months ago may not reflect your current life.

**5. Exploration prevents stagnation.**
TikTok dedicates roughly 50% of recommendations to exploration. A personal model should similarly test hypotheses about the user: "You seem focused in the morning -- let me verify this is still true."

### 18.2 What Does NOT Transfer

**1. Scale-dependent techniques.** Collaborative filtering ("users like you also liked...") requires millions of users. A personal model has exactly one user. Content-based and sequential approaches transfer; collaborative filtering does not.

**2. The social/viral layer.** TikTok's progressive batch testing (200 -> 1K -> 100K viewers) is irrelevant for a personal model. There's no audience to test against.

**3. Creator-side optimization.** Half of TikTok's system is about matching content to users across a marketplace. A personal model has no content marketplace.

**4. Ad revenue optimization.** The commercial objectives that constrain TikTok's recommendations don't apply to a personal tool.

### 18.3 The Minimum Viable Recommendation Loop

Based on TikTok's architecture, the minimum viable personal behavior model needs:

```
1. OBSERVE: Capture implicit behavioral signals
   - What the user is doing (app, document, activity)
   - How long they do it (dwell time)
   - Context (time, location, energy indicators)
   - Transitions (what follows what)

2. STORE: Maintain a lightweight feature store
   - Activity embeddings (what activities cluster together)
   - Temporal patterns (when do you do what)
   - Recency-weighted history (exponential decay)

3. MODEL: Simple but frequently updated
   - Predict: "What should I focus on next?"
   - Predict: "Am I in a productive state?"
   - Predict: "What's draining my energy?"
   - Update model after each significant observation

4. SERVE: Surface insights/recommendations
   - Not as a feed, but as nudges, reflections, or suggestions
   - Include exploration: test hypotheses about the user

5. REPEAT: Close the loop quickly
   - TikTok updates every minute
   - A personal model could update per-session or per-day
   - The key: shorter loops = faster learning
```

### 18.4 Architecture Recommendations

Drawing from Monolith's design:

1. **Use collisionless embeddings** for activity/context features. A cuckoo hashmap is overkill for one user, but the principle of unique, non-colliding feature representations matters.

2. **Implement expirable features**. Interests that haven't been observed in N days should decay and eventually be pruned, exactly like Monolith's expirable embeddings.

3. **Separate training from serving**. Even at personal scale, the model that generates insights should be updated asynchronously from the data collection pipeline.

4. **Start with the Algo 101 formula pattern**:
   ```
   Score = P_productive x V_productive + P_energizing x V_energizing + E_focus_time x V_focus + P_aligned_with_goals x V_goals
   ```
   Where V values are user-tunable weights reflecting personal priorities.

5. **On-device / local-first**. TikTok's approach is server-side, but the principles transfer to federated or fully local architectures. Privacy-preserving approaches like on-device processing with differential privacy are well-suited.

### 18.5 Key Insight

The deepest lesson from TikTok is not technical -- it's about **product design that generates clean signals**. TikTok's full-screen, one-at-a-time, swipe-to-dismiss interface generates unambiguous behavioral data. The equivalent for a personal behavior model is designing observation points that capture clear, interpretable signals about what the user is doing and how they feel about it.

---

## 19. Source Bibliography

### Primary Sources (TikTok/ByteDance Official)

1. [How TikTok recommends videos #ForYou - TikTok Newsroom (June 2020)](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)
2. [Introduction to the TikTok recommendation system - TikTok Transparency](https://www.tiktok.com/transparency/en/recommendation-system)
3. [An update on our work to safeguard and diversify recommendations - TikTok Newsroom](https://newsroom.tiktok.com/en-us/an-update-on-our-work-to-safeguard-and-diversify-recommendations)
4. [TikTok Transparency Center](https://www.tiktok.com/transparency/en-us/)
5. [How TikTok recommends content - TikTok Support](https://support.tiktok.com/en/using-tiktok/exploring-videos/how-tiktok-recommends-content)

### Academic Papers

6. [Monolith: Real Time Recommendation System With Collisionless Embedding Table (arXiv, 2022)](https://arxiv.org/abs/2209.07663)
7. [Deep Retrieval: Learning A Retrievable Structure for Large-Scale Recommendations (arXiv, 2020)](https://arxiv.org/abs/2007.07203)
8. [HLLM: Enhancing Sequential Recommendations via Hierarchical Large Language Models (2024)](https://arxiv.org/abs/2409.12740)
9. [TikTok and the Art of Personalization: Investigating Exploration and Exploitation (WebConf 2024)](https://arxiv.org/abs/2403.12410)
10. [Analyzing User Engagement with TikTok's Short Format Video Recommendations (CHI 2024)](https://dl.acm.org/doi/10.1145/3613904.3642433)
11. ["They've Over-Emphasized That One Search": Controlling Unwanted Content on TikTok's FYP (CHI 2025)](https://arxiv.org/html/2504.13895v1)
12. [A commentary of TikTok recommendation algorithms in MIT Technology Review 2021 (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2667325821002235)
13. [Progressive Layered Extraction (PLE) - Multi-Task Learning for Personalized Recommendations (RecSys 2020)](https://dl.acm.org/doi/10.1145/3383313.3412236)
14. [Magnus: A Holistic Approach to Data Management for Large-Scale ML Workloads (VLDB 2025)](https://dl.acm.org/doi/10.14778/3750601.3750620)
15. [Counting How the Seconds Count: Understanding Algorithm-User Interplay in TikTok (arXiv, 2025)](https://arxiv.org/abs/2503.20030)

### Key Essays & Analyses

16. [TikTok and the Sorting Hat - Eugene Wei (August 2020)](https://eugenewei.substack.com/p/tiktok-and-the-sorting-hat)
17. [Tiktok and "Seeing Like an Algorithm" - a16z (2020)](https://a16z.com/podcast/16-minutes-on-the-news-41-tiktok-and-seeing-like-an-algorithm/)
18. [The Secret Sauce of TikTok's Recommendations - Shaped.ai](https://www.shaped.ai/blog/the-secret-sauce-of-tik-toks-recommendations)
19. [How TikTok Wins The Social Media Recommendation System War - Lee Han Chung](https://leehanchung.github.io/blogs/2020/02/18/Tik-Tok-Algorithm/)
20. [Nobody Tells You What's Actually Inside TikTok's Algorithm - BuildWithAWS](https://buildwithaws.substack.com/p/most-engineers-miss-whats-really)

### Investigative Journalism

21. [Inside TikTok's Dangerously Addictive Algorithm - WSJ (Online Journalism Awards)](https://awards.journalists.org/entries/inside-tiktoks-dangerously-addictive-algorithm/)
22. [NYT Column: How TikTok Keeps You Watching - Ben Smith](https://bensmith.ghost.io/nyt-column-how-tiktok-keeps-you-watching/)
23. [Leaked TikTok Doc Reveals Its Obvious Secret to an Addictive Feed - Gizmodo](https://gizmodo.com/leaked-tiktok-doc-reveals-its-obvious-secret-to-an-addi-1848166901)
24. [TikTok's Secret Algorithm Unveils in Leaked Document 'Algo 101' - TechTimes](https://www.techtimes.com/articles/269024/20211206/tiktok-algo-101-leaked-document-tiktok-secret-algorithm-tiktok.htm)

### Technical Deep Dives

25. [Deep Dive: How to Build the TikTok Recommender System End-to-End - The AI Edge Newsletter](https://newsletter.theaiedge.io/p/deep-dive-how-to-build-the-tiktok)
26. [Monolith Paper Summary - Dhruvil (Substack)](https://dhruvil.substack.com/p/paper-summary-monolith-real-time)
27. [Monolith Paper Review - Shivam Rana](https://shivamrana.me/2022/10/tiktok-monolith-review/)
28. [TikTok-like Recommender Algorithm Implementation - GitHub Gist](https://gist.github.com/ruvnet/6217ea3bd75cc0c27522965965e7383b)
29. [Leaked Info Reveals How TikTok's Algorithm Works - DeepLearning.ai](https://www.deeplearning.ai/the-batch/what-makes-tiktok-tick/)
30. [TikTok Algorithm 2026: How the FYP Really Works - Beatstorapon](https://beatstorapon.com/blog/tiktok-algorithm-the-ultimate-guide/)

### Community Discussion

31. [Monolith: The Recommendation System Behind TikTok - Hacker News](https://news.ycombinator.com/item?id=35573624)
32. [ByteDance's Recommendation System - Hacker News](https://news.ycombinator.com/item?id=42468362)
33. [TikTok reveals details of how its algorithm works - Hacker News](https://news.ycombinator.com/item?id=24431975)

### Open-Source Implementation

34. [ByteDance Monolith - GitHub](https://github.com/bytedance/monolith)
35. [ByteDance HLLM - GitHub](https://github.com/bytedance/HLLM)
