# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

IfOnlyYouCouldTalkToTheMonsters is a Doom-style raycasting 3D game engine in Python/Pygame.
It reads actual Doom WAD files, implements BSP tree traversal, segment rendering, z-buffer

## Running

```bash

uv run python doom.py E1M1 1    # map_name, difficulty (1=easy, 2=hard)
```

There are no tests or linting configurations in this project.

## Dependencies

The project uses the uv package manager.   The pyproject.toml file contains the dependencies which include
pygame ollama numpy numba

ollama will be used for NPC dialogue, with `llama3.2:latest` pulled locally.

## Architecture 

Entry point: [doom.py](doom.py). Reads `.wad` files from `wad/`.

Uses **BSP tree** ([bsp.py](bsp.py)) to traverse level geometry in correct back-to-front order for the segment renderer ([seg_handler.py](seg_handler.py)). Uses a **z-buffer** in [view_renderer.py](view_renderer.py) for sprite occlusion.
