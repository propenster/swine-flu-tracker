# Use the modern Miniconda base
# Force standard Intel architecture to match Heroku and fix Bioconda missing packages
FROM --platform=linux/amd64 continuumio/miniconda3:latest

# (The rest of your Dockerfile stays exactly the same)
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the environment file first to leverage Docker cache
COPY environment.yml .

# Create the Conda environment (Conda in this image is modern and fast)
RUN conda env create -f environment.yml -n swine_flu_tracker_env

# Ensure the conda environment is active for subsequent commands
SHELL ["conda", "run", "-n", "swine_flu_tracker_env", "/bin/bash", "-c"]

# Clone the OctoFLU repository directly into the container
RUN git clone https://github.com/flu-crew/octoFLU.git /opt/octoFLU

# Copy your data and application logic
# (Assuming your local folders are mapped or copied)
COPY . /app

# Expose the FastAPI port (for when you run your web API)
EXPOSE 8000

# Entrypoint: Currently set to run your pipeline. 
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "swine_flu_tracker_env", "python", "/app/run_all.py"]