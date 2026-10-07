#!/usr/bin/env Rscript
# Installs the R packages listed in a requirements file, by default
# src/r/requirements.txt. The file has one package per line, optionally with a
# minimum version ("ggplot2>=3.5.0"); "#" starts a comment. Packages that are
# missing or older than the minimum version are installed from CRAN into the
# user library; everything else is left untouched.
#
# Usage: Rscript src/r/utils/install_packages.R [requirements.txt]

args <- commandArgs(trailingOnly = TRUE)
file <- if (length(args) >= 1) args[1] else "src/r/requirements.txt"
if (!file.exists(file)) stop("Requirements file not found: ", file)

# Parse the requirements ------------------------------------------------------

lines <- trimws(sub("#.*$", "", readLines(file, warn = FALSE)))
lines <- lines[nzchar(lines)]
pattern <- "^([A-Za-z][A-Za-z0-9.]*)(?:\\s*>=\\s*([0-9][0-9.-]*))?$"
matches <- regmatches(lines, regexec(pattern, lines, perl = TRUE))
invalid <- lines[lengths(matches) == 0]
if (length(invalid) > 0) {
  stop("Invalid requirement(s) in ", file, ": ", paste(invalid, collapse = ", "),
       "\nExpected 'package' or 'package>=version'.")
}
packages <- vapply(matches, `[`, character(1), 2)
minimum  <- vapply(matches, `[`, character(1), 3)  # "" when no version is given
names(minimum) <- packages

if (length(packages) == 0) {
  cat("No R packages listed in", file, "\n")
  quit(status = 0)
}

# Find packages that are missing or too old -----------------------------------

needs_install <- function(package) {
  if (!requireNamespace(package, quietly = TRUE)) return(TRUE)
  nzchar(minimum[[package]]) && packageVersion(package) < package_version(minimum[[package]])
}
todo <- packages[vapply(packages, needs_install, logical(1))]

if (length(todo) == 0) {
  cat("All R packages are up to date:", paste(packages, collapse = ", "), "\n")
  quit(status = 0)
}

# Install into the user library ------------------------------------------------

# The user library may not exist yet (R only adds existing directories to
# .libPaths()); create it so that the installation does not need root rights.
lib <- Sys.getenv("R_LIBS_USER")
if (nzchar(lib)) {
  dir.create(lib, recursive = TRUE, showWarnings = FALSE)
  .libPaths(c(lib, .libPaths()))
}

# CRAN mirror: keep a configured repository (e.g. Posit Package Manager with
# binaries in CI), otherwise use the CRAN cloud mirror.
repos <- getOption("repos")
if (is.null(repos) || !"CRAN" %in% names(repos) || identical(repos[["CRAN"]], "@CRAN@")) {
  repos["CRAN"] <- "https://cloud.r-project.org"
}

cat("Installing R packages:", paste(todo, collapse = ", "), "\n")
install.packages(todo, repos = repos, quiet = TRUE)

# Verify ----------------------------------------------------------------------

failed <- todo[vapply(todo, needs_install, logical(1))]
if (length(failed) > 0) {
  stop("Could not install or update: ", paste(failed, collapse = ", "))
}
cat("Installed R packages:", paste(todo, collapse = ", "), "\n")
