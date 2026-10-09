FROM continuumio/miniconda3:latest

RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY environment.yml .

RUN conda env create -f environment.yml -n swine_flu_tracker_env

# SHELL ["conda", "run", "-n", "swine_flu_tracker_env", "/bin/bash", "-c"]

RUN git clone https://github.com/flu-crew/octoFLU.git /opt/octoFLU

COPY run_all.py /app/run_all.py

RUN /opt/conda/envs/swine_flu_tracker_env/bin/python -c "import Bio; print('biopython', Bio.__version__)"

ENTRYPOINT ["/opt/conda/envs/swine_flu_tracker_env/bin/python", "/app/run_all.py"]