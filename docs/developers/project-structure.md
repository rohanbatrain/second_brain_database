# Project Structure

## Overview

The **Second Brain Database (SBD)** project is organized in a modular and scalable manner to facilitate easy development, maintenance, and future extensions. The system uses Django for backend operations and Flask for frontend functionalities. 

This document provides a breakdown of the project structure, detailing the various files and directories that make up the system, and explaining their roles in the project.

---

## Important Notice

Please note that this documentation may be out of date, as **Rohan** (the sole developer of this project) is actively working on the system as a full-stack developer. Updates and new features are being added regularly, but there may be times when the documentation lags behind the actual implementation.

---

## Directory Structure

```
.
├── .gitignore
├── LICENSE
├── README.md
├── pyproject.toml
├── sbd_config.json                # Configuration file for the project
├── mkdocs.yml                     # MkDocs configuration for documentation
├── docs/                          
│   ├── project-structure.md       # Documentation on project structure
│   └── getting-started.md         # Getting started guide for the project
├── src/                           
│   ├── __init__.py                # Initialization for the src module
│   ├── Second_Brain_Database.egg-info/
│   │   ├── PKG-INFO
│   │   ├── SOURCES.txt
│   │   ├── top_level.txt
│   │   └── dependency_links.txt
│   ├── sbd_rohanbatrain/           # Core logic of the system
│   │   ├── __init__.py
│   │   ├── main.py                # Main entry point for the system
│   │   ├── sleep.py               # Sleep management feature
│   │   ├── utilities/             
│   │   │   ├── __init__.py
│   │   │   └── config_related.py  # Configuration utility functions
│   │   ├── config_files/          
│   │   │   ├── __init__.py
│   │   │   └── config.py          # Configuration file for the system
│   │   ├── external_sources/      
│   │   │   ├── youtube/           # YouTube integration
│   │   │   └── spotify/           # Spotify integration
│   │   ├── integrations/          
│   │   │   ├── __init__.py
│   │   │   ├── todoist.py         # Todoist integration
│   │   │   └── telegram.py        # Telegram integration
│   │   ├── frontend/              
│   │   │   ├── flask_app/         
│   │   │   │   ├── flashcards/    # Flashcards feature for the frontend
│   │   │   │   └── templates/     # HTML templates for frontend
│   │   ├── database/              
│   │   │   ├── __init__.py
│   │   │   └── db.py              # Database connection and handling
│   │   ├── features/              
│   │   │   ├── cognitive_training/    # Cognitive training features
│   │   │   │   └── random_quote_for_though.py
│   │   │   ├── expense_tracker/      # Expense tracking features
│   │   │   │   ├── expense_tracker.py
│   │   │   │   ├── expense_tracker_update/
│   │   │   │   └── expense_tracker_delete/
│   │   │   ├── habit_tracker/        # Habit tracking features
│   │   │   ├── project/              # Project management features
│   │   │   │   ├── project_update/
│   │   │   │   └── project_delete/
│   │   │   ├── quotes_management/    # Quotes management features
│   │   │   │   └── quotes_create.py
│   │   │   ├── item_usage_tracker/   # Item usage tracking features
│   │   │   ├── playlist/             # Playlist features
│   │   │   ├── artificial_intelligence/  # AI-related features
│   │   │   ├── tasks/                # Task management features
│   │   │   │   ├── tasks_update/
│   │   │   │   └── tasks_delete/
│   │   │   ├── meal_tracker/         # Meal tracking features
│   │   │   ├── inventory/            # Inventory management features
│   │   │   ├── network/              # Network features
│   │   │   ├── food_recipes/         # Food recipe features
│   │   │   ├── mood_tracker/         # Mood tracking features
│   │   │   ├── body_weight_tracker/  # Body weight tracking features
│   │   │   ├── water_intake_tracker/ # Water intake tracking features
│   │   │   ├── label/                # Labeling system features
│   │   │   ├── flashcards/           # Flashcard features
│   │   │   ├── restaurants/          # Restaurants management features
│   │   │   └── __init__.py
├── tests/                           
│   ├── manual-tests/               
│   │   ├── sleep.py               # Test case for the sleep feature
│   ├── config_files/               
│   │   └── config.py              # Test cases for config-related features
└── sbd_config.example.json         # Example configuration file for the project
```

---

## Key Components

### 1. **`sbd_config.json`**
   - This is the configuration file for the entire system. It holds global settings that help the system function, such as API keys, user preferences, and integration settings.

### 2. **`mkdocs.yml`**
   - Configuration for the **MkDocs** tool used to generate static documentation for the project.

### 3. **`docs/`**
   - Documentation files for understanding the project structure and how to set up the system.
     - **`project-structure.md`**: A detailed explanation of the project’s internal structure.
     - **`getting-started.md`**: A step-by-step guide for setting up the project and running it locally.

### 4. **`src/`**
   - The source code of the project is housed here. The main directory is `sbd_rohanbatrain`, and it contains several subdirectories:
     - **`features/`**: Implements various features like task management, expense tracking, habit tracking, etc.
     - **`integrations/`**: Handles integration with third-party services like Todoist, Telegram, YouTube, and Spotify.
     - **`frontend/`**: Contains the **Flask** web application, including templates and static files.
     - **`database/`**: Responsible for all database operations and configurations.
     - **`utilities/`**: Helper functions and utilities for the project’s internal use.

### 5. **`tests/`**
   - The tests directory contains unit tests and manual tests for different features of the project. These are crucial for verifying the functionality of the system.

### 6. **`sbd_config.example.json`**
   - A template configuration file that shows users how to set up their own `sbd_config.json`.

---

## Conclusion

This document outlines the overall project structure of the **Second Brain Database** system. It provides an in-depth overview of the project's directories and files, highlighting the purpose of each component. 

For further details on setting up the project or contributing, please refer to the other documentation sections, such as the **Getting Started Guide** and the **Feature Documentation**.