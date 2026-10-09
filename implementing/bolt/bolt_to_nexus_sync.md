# Syncing Bolt.new Projects into AgentNexus

This guide describes how to import a working full-stack prototype from Bolt.new into the AgentNexus repository.

---

## Step 1: Export from Bolt.new

In the Bolt.new UI:
- Click the **GitHub** icon in the top header and push to a new GitHub repository, OR
- Click the **Download Project** icon to download a `.zip` archive.

---

## Step 2: Unpack into Monorepo UI Directory

Assuming you downloaded `project.zip`:

```bash
# 1. Unzip into a staging directory
mkdir -p /tmp/bolt_import
unzip ~/Downloads/project.zip -d /tmp/bolt_import

# 2. Copy the frontend assets into the GUI dashboard directory
cp -r /tmp/bolt_import/src/* gui/agent_dashboard/web/

# 3. Clean up staging
rm -rf /tmp/bolt_import
```

---

## Step 3: Run Daily Coder Policy Review & Tests

Once the files are placed in the repository:
```bash
# Run PolicyGateway check to verify no dangerous binaries or leaks
python -m ai_agents_repo.validate --phase F0

# Execute acceptance tests
python -m unittest discover -s gui/tests -v
```
