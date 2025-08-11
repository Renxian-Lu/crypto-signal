# Crypto Signal

## Setup Instructions

### Deactivate any existing environment

```
conda deactivate
```

### Navigate to the project directory

```
cd C:\Code\crypto-signal
```

### Build a virtual environment

```
python -m venv .venv
```

### Activate the virtual environment

```
.venv\Scripts\activate
```

### Excute the project

```
uvicorn api.main:app --reload --port 8000
```
