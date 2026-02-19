# Introducing Open Fred

OpenFred is a super light weight Agent Orchestration platform designed with two key consideration:
- Maximize utilization of locally-run open source models, and
- Ease of use 


# LLM Settings: Local (Ollama) vs API

By default OpenFred connects to Gemma3:4b LLM running on a local instance of Ollama. You may connect to any other LLM available via Ollama; simply download and run the LLM locally (or via Ollama cloud) and OpenFred can connect without the need for any API credentials. Simply head over to Settings and set the correct LLM you are using

You may also connect to any other LLM via API Keys, also found under settings. Note that an API Key is required in the Settings menu


# Quick Start

- download and run [Ollama](https://ollama.com/) - we recommend starting with [Gemma3:4b](https://ollama.com/library/gemma3)
- Clone this repo
- cd <repo dir>
- python main.py

  

![OpenFred](http://187.77.27.73:32769/wp-content/uploads/2026/02/OpenFred-1.png)
