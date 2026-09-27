# Runtime

The repository includes a small executable control plane in `clipme.py`.

It deliberately does not hard-code one AI provider. AI agents generate/repair the project artifacts; the runtime validates and assembles them.

## Requirements
- Python 3.10+
- packages in requirements.txt
- FFmpeg + ffprobe for assembly/probing

## Create a project

```bash
python clipme.py init work/demo \
  --profile short-90s \
  --title "Demo" \
  --language th \
  --duration 60
```

For long work:

```bash
python clipme.py init work/documentary --profile longform --duration 3600
python clipme.py init work/feature --profile film --duration 7200
```

## Validate contracts

```bash
python clipme.py validate work/demo
```

## Render manifest

After shot/scene/sequence production, list ordered rendered units:

```json
{
  "project_id": "DEMO",
  "segments": [
    {"id":"SEQ_001","path":"renders/sequences/SEQ_001.mp4"},
    {"id":"SEQ_002","path":"renders/sequences/SEQ_002.mp4"}
  ],
  "output": "masters/master.mp4"
}
```

All segments should already conform to the project's delivery format.

## Assemble one master

```bash
python clipme.py assemble work/demo
```

The command uses FFmpeg and re-encodes to H.264/AAC for reliable assembly.

## Probe output

```bash
python clipme.py probe work/demo/masters/master.mp4
```

## Release gate

QC must explicitly be PASS:

```bash
python clipme.py gate work/demo
```

The runtime is intentionally small. Future provider/render adapters should attach around these stable contracts rather than changing them.
