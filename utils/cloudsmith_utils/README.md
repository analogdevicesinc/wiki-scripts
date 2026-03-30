# Cloudsmith Utils

This directory is synced from an internal (innersource) repository via GitHub Actions.

## Contributing

Open source contributors are welcome to submit PRs to this repository.

### Contribution flow

1. Submit your PR to this repository
2. We review and merge your changes
3. We cherry-pick the changes to the innersource repository
4. The sync workflow runs and may create a PR:
   - If the cherry-pick is identical, no sync PR is created
   - If there are conflicts, the sync PR will require manual resolution

### Sync protection

A CI check runs on sync PRs to detect if local changes would be overwritten.
If this repository has commits touching the synced files that haven't been
cherry-picked to innersource yet, the check fails and blocks auto-merge.

### For maintainers

After merging an open source contribution, cherry-pick the changes to
innersource promptly. If a sync PR fails the conflict check:

1. Cherry-pick the missing changes to innersource, or
2. Manually resolve the differences before merging
