# Project Structure

The project is organized as follows:

```
./second_brain_database/
    ├── docs/                     # Documentation for the project
    ├── src/
        ├── sbd_rohanbatrain/     # Core logic of the system (existing code)
        │   ├── main.py
        │   └── sleep.py
    ├── tests/  
```

- **`docs/`**: Contains all the documentation related to the project.
- **`src/`**: The source code directory.
  - **`sbd_rohanbatrain/`**: Core Python-based logic (your existing code).
  - **`second_brain_api/`**: Contains the Django project, which is structured into multiple apps (API and frontend).
    - **`api/`**: Handles API endpoints, models, and serialization logic.
    - **`frontend/`**: Responsible for serving templates and static files.