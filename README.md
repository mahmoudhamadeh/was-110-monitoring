<h1>WAS-110 Monitoring Dashboard</h1>
<p>This project provides a web dashboard for monitoring WAS-110 SFP stick metrics.</p>
<h2>Project Structure</h2>
<pre><code>sfp_monitor/
├── app.py                  # Python Flask backend
├── Dockerfile              # Docker image build instructions
├── requirements.txt        # Python dependencies
├── static/                 # Static web files
│   └── index.html          # Frontend dashboard
├── .env                    # Environment variables (sensitive data)
└── compose.yaml            # Docker Compose configuration
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
<p>(No quotes around the password. Add <code>.env</code> to <code>.gitignore</code> if using Git.)</p>
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
<p><code>http://localhost:5000</code></p>
<p>Use the buttons and slider above the graphs to adjust the visible time window.</p>
<h2>Troubleshooting</h2>
<ul>
<li><strong><code>Authentication failed</code></strong>:
Double-check <code>SFP_ROOT_PASSWORD</code> in your <code>.env</code> file.</li>
<li><strong>SFP Stick SSH unresponsiveness over time</strong>:
The <code>app.py</code> polling interval is set to 5 minutes (<code>time.sleep(300)</code>). If issues persist, consider increasing this interval further.</li>
</ul>
