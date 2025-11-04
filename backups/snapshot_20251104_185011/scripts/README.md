# Scripts Directory

## Structure

```
scripts/
├── startall/          # Unified startup system
│   ├── start_all.sh           # Start all services
│   ├── stop_services.sh       # Stop all services
│   ├── attach_service.sh      # View logs in current terminal
│   ├── open_service_terminal.sh  # Open logs in new terminal
│   └── open_all_terminals.sh  # Open all logs in separate terminals
│
└── manual/            # Individual service scripts
    ├── start_fastapi_server.py
    ├── start_voice_worker.py
    ├── start_celery_worker.py
    ├── start_celery_beat.py
    └── start_flower.py
```

## Quick Start

From project root:

```bash
# Start everything
./start.sh

# Stop everything
./stop.sh
```

## Advanced Usage

### Unified Startup (Recommended)
```bash
# Start all services
scripts/startall/start_all.sh

# Stop all services
scripts/startall/stop_services.sh

# View service logs
scripts/startall/attach_service.sh fastapi

# Open service in new terminal
scripts/startall/open_service_terminal.sh celery_worker

# Open all services in separate terminals
scripts/startall/open_all_terminals.sh
```

### Manual Startup (Individual Services)
```bash
# Start services individually
python scripts/manual/start_fastapi_server.py
python scripts/manual/start_voice_worker.py
python scripts/manual/start_celery_worker.py
python scripts/manual/start_celery_beat.py
python scripts/manual/start_flower.py
```

## Service Management

All logs: `logs/`
All PIDs: `pids/`
