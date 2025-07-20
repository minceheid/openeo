# Contributing

TBD

# Publishing a New Release

To trigger a build that creates and attaches a zip file of the repository to a GitHub Release, follow these steps:

1. Ensure all your changes are committed and pushed to the main branch (or the branch you want to release).
2. Go to the [Releases](https://github.com/minceheid/openeo/releases) page of this repository.
3. Click on "Draft a new release".
4. Fill in the tag version (e.g., `v1.2.3`), release title, and description as needed.
5. Click "Publish release".

Once the release is published, the GitHub Actions workflow will automatically:
- Create a zip file of the repository contents (excluding git related folders)
- Attach the zip file to the release

No manual upload is required. The process is fully automated.

If you encounter any issues, please check the Actions tab for workflow logs or contact a repository maintainer.
