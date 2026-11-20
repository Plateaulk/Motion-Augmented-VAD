# Motion-Augmented VAD

A Vue/Flask pipeline for motion-guided augmentation in weakly supervised video
anomaly detection on ShanghaiTech and UCF-Crime.
MotionStreamer generates motion from text, ComfyUI runs Wan2.1-VACE to synthesize
video, and ProDisc-VAD trains on real and generated video features.

## Setup

The pipeline targets Linux with an NVIDIA GPU, Python 3.10–3.12, CUDA-compatible
PyTorch, FFmpeg, EGL/OpenGL and Node.js 22.12 or later.
Supply datasets, backgrounds and model weights locally.

<details>
<summary>Install upstream code and dependencies</summary>

From the repository root, clone the pinned revisions and apply the local changes.

```bash
mkdir -p external
git clone https://github.com/zju3dv/MotionStreamer.git external/MotionStreamer
git -C external/MotionStreamer checkout 9ecbb2569c3cfa9b91034f17cb6478153b9e65c7
git clone https://github.com/modadundun/ProDisc-VAD.git external/ProDisc-VAD
git -C external/ProDisc-VAD checkout cd885300d7ec02773f2d686ecdb34f97354a3f14
git clone https://github.com/Comfy-Org/ComfyUI.git external/ComfyUI
git -C external/ComfyUI checkout 28eaab608bc34c4e3b1886b1bddbb429453249d8

cp ProDisc-VAD/*.py external/ProDisc-VAD/
cp MotionStreamer/*.py external/MotionStreamer/
cp MotionStreamer/options/option_transformer.py external/MotionStreamer/options/
cp MotionStreamer/utils/PYTORCH3D_LICENCE external/MotionStreamer/utils/

python -m pip install setuptools==80.9.0 wheel
python -m pip install --no-build-isolation -r MotionStreamer/requirements.txt -r VADSystem/backend/requirements.txt
```

Install `external/ComfyUI/requirements.txt` in a separate environment with
CUDA-compatible PyTorch.
The backend accepts `COMFYUI_PYTHON`, `MOTIONSTREAMER_PYTHON` and `PRODISC_PYTHON`
for service interpreters and `CKPT_PATH` for detector weights.
[Backend settings](VADSystem/backend/config.py)

</details>

<details>
<summary>Model files</summary>

Download the generation assets and place them under the upstream directories shown below.
All three video modes use the same Wan2.1-VACE weights.
[MotionStreamer assets](https://github.com/zju3dv/MotionStreamer) ·
[ComfyUI Wan2.1-VACE weights](https://comfyanonymous.github.io/ComfyUI_examples/wan/#vace-reference-image-to-video)

| `external/MotionStreamer/` | `external/ComfyUI/` |
| --- | --- |
| `Causal_TAE/net_last.pth` | `models/diffusion_models/wan2.1_vace_14B_fp16.safetensors` |
| `Experiments/t2m_model/latest.pth` | `models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors` |
| `sentencet5-xxl/` | `models/vae/wan_2.1_vae.safetensors` |
| `reference_end_latent_t2m_272.npy`, `humanml3d_272/mean_std/`, `smpl_models/` | |

Feature extraction and live scoring use OpenAI CLIP ViT-B/16.
CLIP downloads the encoder on first use.
For an offline server, place `ViT-B-16.pt` in `~/.cache/clip/` beforehand.
[OpenAI CLIP model files](https://github.com/openai/CLIP/blob/main/clip/clip.py)

</details>

## Start the services

Start each service in its own terminal.
In the backend terminal, set the two keys and point `DATASET_PATH` to your dataset root.

```bash
export DATASET_PATH=/path/to/datasets
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

| Working directory | Command |
| --- | --- |
| `VADSystem/backend` | `python app.py` |
| `external/MotionStreamer` | `python motion_server.py --port 5100` |
| `external/ComfyUI` | `python main.py --listen 127.0.0.1 --port 8188` |
| `VADSystem/frontend` | `npm ci && npm run dev` |

## Workflow

1. **Upload the original dataset to the server.**

   Copy the ProDisc-VAD package for the dataset you plan to use into `DATASET_PATH`
   on the machine running Flask.

   Each dataset folder needs its original ten-crop features, `train_split_10crop.txt`,
   `test_split_10crop.txt` and `GT/video_label_10crop.pickle`.
   Keep each test video's ten crops together in order from 0 to 9.
   [ProDisc-VAD dataset downloads](https://github.com/modadundun/ProDisc-VAD/tree/cd885300d7ec02773f2d686ecdb34f97354a3f14#dataset-preparation)

   - In `shanghaitech/`, place the features in `SH_clip_video_features/`
     and the frame annotations in `GT/frame_label.pickle`.
   - In `ucf-crime/`, use `UCFClipFeatures/` and `GT/ucf_gt_upgate.pickle`.

2. **Upload scene backgrounds.**

   Open `http://127.0.0.1:6006`, register or sign in, and select **SHT** or **UCF**.
   For text-only generation, go directly to step 5.

   For image- or motion-guided generation, open **Manage Files → Upload → Backgrounds**
   and select your scene images. Preview them in **Backgrounds**.
   Continue with step 3 for motion guidance or step 5 for image guidance.

3. **Generate or reuse a motion in Mask Generator.**

   Under **Generate Motion**, describe one action, for example “a person walks to the left.”
   Enter a filename, choose an output folder and click **Generate**.

   Select the result in **Motion List**.
   To reuse an earlier motion, select its folder and search the list.

4. **Render the motion from the desired viewpoint.**

   In **Render Settings**, choose a background.
   Set **Yaw** to rotate the person and their path, **Height** for camera elevation
   and **Distance** for framing. Choose a resolution preset or enter the width and height.
   Set the render filename and output folder, then click **Start Render**.

   To compare views, render the same motion again with another angle, distance or
   background and a new filename. In **Render Result**, preview the composite
   **Reference** and its **Mask**. Click **Use for V2V** on the version you want.

5. **Generate a video in Video Generator.**

   Check that the page shows **ComfyUI Running**.
   Choose a mode, enter a prompt, set the duration (1–10 seconds) and resolution,
   and choose an output folder and unique filename. Optionally add a negative prompt.
   Click **Start Generate** and preview the resulting video.

   - **T2V** (text to video) uses the scene and action described in the prompt.
   - **I2V** (image to video) uses an uploaded background and a prompt describing
     the action.
   - **V2V** (video to video) uses the render from step 4 or a **Motion Pair**
     selected in this tab. Check its reference and mask, describe the intended scene,
     and optionally select a background.

6. **Extract features in Data Process.**

   Select the output folder from step 5, choose the finished video and preview it.
   Under **Feature Extract**, select **ShanghaiTech** or **UCF-Crime**, choose a
   destination (default `system_extracted`), enter a unique ID starting with `Gen`
   and click **Extract**.

   ShanghaiTech treats generated IDs as anomalous.
   For UCF-Crime, include `_normal_` in IDs for normal clips, such as `Gen_normal_001`.

   The extractor takes the first frame of each complete 16-frame segment and encodes
   ten spatial crops separately with CLIP ViT-B/16. It writes `<id>_0.npy` through
   `<id>_9.npy` as float32 for ShanghaiTech or float16 for UCF-Crime.
   Both profiles accept video files. The ShanghaiTech command-line extractor also
   accepts numbered frame folders.
   [Extractor](ProDisc-VAD/extract_features.py) ·
   [Crop order](https://github.com/nwpu-zxr/VadCLIP/blob/main/src/crop.py) ·
   [Sampling interval](https://github.com/nwpu-zxr/VadCLIP/issues/1)

7. **Train a detector in Training.**

   Select the matching dataset, name the experiment and set the iteration count.

   For a real-only run, turn **Synthetic Samples** off.
   For a mixed run, turn it on, select the directory from step 6 and set
   **Synthetic Crop Ratio** per class. The default extraction folders appear as
   **System Feature (SHT)** and **System Feature (UCF)**.

   Enable **Snapshot** for evaluation history and the best checkpoint,
   then click **Start Train**.

8. **Evaluate the checkpoint in Inference.**

   Select the trained model and click **Start Infer**.
   The page scores the original test split and plots its anomaly scores.
   On completion, check the frame-level ROC AUC and the reported coverage of videos
   and annotated frames.

9. **Compare models in Analysis.**

   Select **Model A** and **Model B**. A percentage beside a name gives the run’s
   highest logged test ROC AUC. The upper plot shows AUC by training iteration.

   Search for a test video in either lower panel to update both models’ frame scores
   for the same video. Shading marks the annotated anomaly intervals.

10. **Try live scoring in Monitor** (optional).

    Click **Authorize Camera**, select a camera and a trained checkpoint,
    set the alert threshold and click **Start Monitor**.
    **Current** shows the latest scored segment.

    After **Stop**, use **Save Results** for the scores as CSV or **Save Curve**
    for the plot.

## Acknowledgements and license

MotionStreamer supplies the motion model and its 272-D representation for HumanML3D.
The renderer uses SMPL, and ComfyUI executes the Wan2.1-VACE workflows.
[MotionStreamer](https://github.com/zju3dv/MotionStreamer) ·
[272-D representation](https://github.com/Li-xingXiao/272-dim-Motion-Representation) ·
[SMPL](https://smpl.is.tue.mpg.de/) · [Wan2.1-VACE](https://github.com/ali-vilab/VACE) ·
[Wan2.1 backbone](https://github.com/Wan-Video/Wan2.1) ·
[ComfyUI](https://github.com/Comfy-Org/ComfyUI)

The detector and training losses come from ProDisc-VAD.
GV-VAD inspired the use of generated videos to augment detector training.
[ProDisc-VAD](https://github.com/modadundun/ProDisc-VAD) ·
[OpenAI CLIP](https://github.com/openai/CLIP) · [GV-VAD](https://github.com/Sumutan/GV-VAD)

The MIT license covers project-authored code.
Third-party code, models and data retain their own terms.
[MIT license](LICENSE) · [MotionStreamer notice](MotionStreamer/LICENSE) ·
[ProDisc-VAD notice](ProDisc-VAD/LICENSE) ·
[PyTorch3D notice](MotionStreamer/utils/PYTORCH3D_LICENCE)
