FROM --platform=linux/amd64 continuumio/miniconda3:latest

RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY environment.yml .

RUN conda env create -f environment.yml -n swine_flu_tracker_env

SHELL ["conda", "run", "-n", "swine_flu_tracker_env", "/bin/bash", "-c"]

RUN git clone https://github.com/flu-crew/octoFLU.git /opt/octoFLU

COPY . /app

#fastapi uvicorn server
EXPOSE 8000

ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "swine_flu_tracker_env", "python", "/app/run_all.py"]