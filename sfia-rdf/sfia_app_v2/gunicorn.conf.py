import multiprocessing

# Bind
bind = "0.0.0.0:5000"

# Workers
# Using sync workers by default. For a blocking CPU-bound ML model,
# creating multiple worker processes allows concurrent NLP requests.
# Calculate workers based on CPU cores, but cap at an appropriate
# number depending on memory constraints of the deployment server.
workers = min(multiprocessing.cpu_count() * 2 + 1, 4)
worker_class = "sync"

# Timeouts
timeout = 120 # Provide ample time for ML processing on slow/cold starts

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
