# Dracula CLI Documentation

The web requests are cached so you don't have to worry about ratelimits for using the same command multiple times in a short period of time

## `help` command

Description: Show help for the CLI
Usage: `dracula --help`


## `all` command

Description: Show all the available apps
Usage: `dracula all`

The output can sometimes be too big to be shown at once in some terminals, to make sure this doesn't happen you can use the --pager flag or if you want the best of the best, use the --tui flag. The --sort option can be used to sort the list of apps based on a specific criteria

### Parameters

- `--sort  TEXT`

  What to use when sorting repos, valid options are `name`, `stars`, `forks`, `size`, `watchers`, `language`, `issues`, `created_at`, `updated_at`, `pushed_at` [default: `stars`]

- `--pager`/`--no-pager`

  Whether to use pagination or not [default: `no-pager`]

- `--tui`/`--no-tui`

  Whether to use a textual use interface or not [default: `no-tui`]

- `--help`

  Show help message for the `all` command.

> **Note:** Either `--pager` or `--tui` can be used at once, not both.


### `show` command

Description: Show install guide and information about the specified app
Usage: `dracula view <APP_NAME>`

By default only the app git repository metadata and the installation instructions are shown. You can optionally also ask for the readme.md file by using the --readme flag.

### Parameters

- `--readme`/`no-readme`

  Whether to use pagination or not [default: `no-readme`]

- `--installation`/`--no-installation`

  Whether to use a textual use interface or not [default: `--installation`]

- `--help`

  Show help message for the `view` command.

### `demo` command

Description: View an approximate demonstration of the dracula theme
Usage: `dracula demo`

The code shown here is same as the dracula template repo. To switch between different programming languages, use the arrow keys left and right. To scroll you can use the mouse or the up and down arrow keys, the page-up and page-down keys also work. To exit, press q

### Parameters

- `--help`

  Show help message for the `demo` command.

### `download` command

Description: Download files for a theme to a specific folder
Usage: `dracula download <APP_NAME>`

This is useful for themes where there is some kind of configuration files required in order to install the theme.

### Parameters

- `--help`

  Show help message for the `downoad` command.
