<!DOCTYPE html>
<html>

<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://stackedit.io/style.css" />
</head>

<body class="stackedit">
  <div class="stackedit__html"><h1 id="was-110-monitoring-dashboard">WAS-110 Monitoring Dashboard</h1>
<p>This project provides a lightweight web dashboard for  <strong>real-time monitoring</strong>  of metrics from the  <strong>WAS-110 SFP stick</strong>. It’s designed to be deployed easily using Docker and runs on a local network with minimal configuration.</p>
<h2 id="file-structure">File Structure</h2>
<pre><code>was-110-monitoring
├── app.py                  # Python Flask backend application
├── Dockerfile              # Docker image build instructions
├── requirements.txt        # Python dependencies
├── static/                 # Static web files
│   └── index.html          # Frontend HTML/JavaScript dashboard
├── .env                    # Environment variables (sensitive data)
└── compose.yaml            # Docker Compose configuration file
</code></pre>
<h2 id="run-using-prebuilt-docker-image">Run Using Prebuilt Docker Image</h2>
<p>Pull and run the latest image from Docker Hub:</p>
<pre><code>services:
  was-110-monitor:
    container_name: sfp_monitor
    restart: unless-stopped
    ports:
      - "5050:5050"
    environment:
      - SFP_ROOT_PASSWORD=YOUR_PASSWORD
      - FETCH_INTERVAL_SECONDS=30
    volumes:
      - sfp_data_volume:/data
    image: mhamadeh/was-110-monitor:latest
volumes:
  sfp_data_volume:
</code></pre>
<p>or</p>
<pre><code>docker run -d \
  --name sfp_monitor \
  -e SFP_ROOT_PASSWORD=YOUR_PASSWORD \
  -e FETCH_INTERVAL_SECONDS=30 \
  -p 5050:5050 \
  -v sfp_data_volume:/data \
  mhamadeh/was-110-monitor:latest
</code></pre>
<h2 id="build-from-source-github">Build From Source (GitHub)</h2>
<p>Clone the Repository</p>
<pre><code>git clone https://github.com/yourusername/was-110-monitoring.git
cd was-110-monitoring` 
</code></pre>
<p>Build the Docker Image</p>
<pre><code>docker build -t was-110-monitor:local .
</code></pre>
<p>Run the Container</p>
<pre><code>docker run -d \
  --name sfp_monitor \
  -e SFP_ROOT_PASSWORD=YOUR_PASSWORD \
  -e FETCH_INTERVAL_SECONDS=30 \
  -p 5050:5050 \
  -v sfp_data_volume:/data \
  was-110-monitor:local
</code></pre>
<h2 id="dashboard-access">Dashboard Access</h2>
<p>Once running, open your browser and visit:</p>
<pre><code>http://localhost:5050
</code></pre>
<h2 id="volume-persistence">Volume Persistence</h2>
<p>The container stores 24 hours rolling historical data in,  history retained across restarts.</p>
<pre><code>/data/sfp_history.json
</code></pre>
</div>
</body>

</html>
