<h1>WAS-110 Monitoring Dashboard</h1>
<p>This project provides a web dashboard for monitoring WAS-110 SFP stick metrics.</p>
<h2>Project Structure</h2>
<pre><code>sfp_monitor/
├── app.py                  # Python Flask backend application
├── Dockerfile              # Docker image build instructions
├── requirements.txt        # Python dependencies
├── static/                 # Static web files
│   └── index.html          # Frontend HTML/JavaScript dashboard
├── .env                    # Environment variables (sensitive data)
└── compose.yaml            # Docker Compose configuration file
</code></pre>
<h2>Setup</h2>
<ol>
<li>
<p><strong>Clone or Create Project Directory:</strong></p>
<pre><code>mkdir sfp_monitor
cd sfp_monitor
mkdir static
</code></pre>
</li>
<li>
<p><strong>Create Project Files:</strong>
Populate <code>app.py</code>, <code>Dockerfile</code>, <code>requirements.txt</code>, <code>static/index.html</code>, and <code>compose.yaml</code> with the provided code.</p>
</li>
<li>
<p><strong>Create <code>.env</code> File:</strong>
In the <code>sfp_monitor</code> directory, create a file named <code>.env</code>:</p>
<pre><code>nano .env
</code></pre>
<p>Add your SFP stick's root password:</p>
<pre><code>SFP_ROOT_PASSWORD=your_actual_sfp_password_here
</code></pre>
<p>(No quotes around the password. Add <code>.env</code> to your <code>.gitignore</code> if using Git.)</p>
</li>
<li>
<p><strong>Build and Run with Docker Compose:</strong>
Navigate to your <code>sfp_monitor</code> directory and execute:</p>
<pre><code>docker compose down --volumes
docker compose build --no-cache
docker compose up -d
</code></pre>
</li>
</ol>
<h2>Usage</h2>
<p>Access the dashboard in your web browser:</p>
<p><code>http://[YOUR_RASPBERRY_PI_IP_ADDRESS]:5050</code></p>
<p>(Replace <code>[YOUR_RASPBERRY_PI_IP_ADDRESS]</code> with your Raspberry Pi's actual IP address on your network.)</p>
<p>Use the buttons (1 Hour, 3 Hours, 6 Hours, 12 Hours) and the slider to adjust the visible time window and scroll through historical data.</p>
<h2>Configuration</h2>
<ul>
<li>
<p><strong>Change Polling Rate:</strong>
To adjust how often data is fetched from the SFP stick and how frequently the dashboard refreshes, follow these steps:</p>
<ol>
<li>
<p><strong>Modify <code>sfp_monitor/app.py</code>:</strong>
Open <code>app.py</code> and change the <code>FETCH_INTERVAL_SECONDS</code> variable to your desired interval in seconds.</p>
<pre><code># app.py
FETCH_INTERVAL_SECONDS = 300 # e.g., 60 for 1 minute, 900 for 15 minutes
</code></pre>
</li>
<li>
<p><strong>Modify <code>sfp_monitor/static/index.html</code>:</strong>
Open <code>static/index.html</code> and change the <code>BACKEND_FETCH_INTERVAL_SECONDS</code> variable to <em>exactly match</em> the value set in <code>app.py</code>.</p>
<pre><code>// static/index.html
const BACKEND_FETCH_INTERVAL_SECONDS = 300; // Must match app.py
</code></pre>
</li>
<li>
<p><strong>Save both files.</strong></p>
</li>
<li>
<p><strong>Rebuild and Restart Docker Container:</strong>
Navigate to your <code>sfp_monitor</code> directory and run:</p>
<pre><code>docker compose down --volumes
docker compose build --no-cache
docker compose up -d
</code></pre>
</li>
<li>
<p><strong>Hard Refresh Browser:</strong>
Clear your browser's cache (<code>Ctrl+Shift+R</code> or Incognito mode) and reload the dashboard page.</p>
</li>
</ol>
</li>
</ul>
<h2>Troubleshooting</h2>
<ul>
<li><strong><code>Authentication failed</code></strong>:
Double-check <code>SFP_ROOT_PASSWORD</code> in your <code>.env</code> file.</li>
<li><strong>SFP Stick SSH unresponsiveness over time</strong>:
The <code>app.py</code> polling interval is set to 5 minutes (<code>time.sleep(300)</code>). If issues persist, consider increasing this interval further.</li>
</ul>

