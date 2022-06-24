<div id="top"></div>

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/GabrielWechta/cans">
    <img src="resources/logo.png" alt="Logo" width="160" height="160">
  </a>

<h3 align="center">CANS</h3>

  <p align="center">
    cans are nicely secure
    <br />
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

## Usage:

### Build and install dependencies

```bash
sudo make
```

### Install the application

```bash
sudp make install
```

## Contributing for Devs

### Bootstrap the repository

This is done only once after having cloned the repository:

```bash
. bootstrap
```

### Initialize the workspace

This needs to be done every time a new session is started:

```bash
. initialize
```

### Run pre-commit hooks

```bash
pre-commit run --all-files
```

### Run tests

```bash
# Run module tests
pytest client
pytest server
pytest common

# Run integration tests
./run_integration_tests

# Run all of the above
./run_full_test_suite
```

<!-- ABOUT THE PROJECT -->

## About The Project

[![Product Name Screen Shot][product-screenshot]](https://example.com)

### Built With

- [Python](https://python.org)
- [Docker](https://docker.com)

## Getting Started

### Prerequisites

### Installation

## Usage

## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#top">back to top</a>)</p>
