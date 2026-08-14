import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config.dart';
import '../../data/local/app_database.dart';
import '../../data/sync/sync_service.dart';
import '../../shared/widgets.dart';
import 'theme_picker.dart';

class HomeActionsSheet extends ConsumerWidget {
  const HomeActionsSheet({
    required this.onFetchLatest,
    required this.onSync,
    super.key,
  });

  final VoidCallback onFetchLatest;
  final VoidCallback onSync;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sync = ref.watch(syncControllerProvider);
    final busy = sync.isLoading || sync.asData?.value.busy == true;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
            AppSpacing.page, AppSpacing.x2, AppSpacing.page, AppSpacing.x3),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const PageHeading(
              title: 'Rail Inspect',
              subtitle: 'Profile, appearance and data controls',
            ),
            const SizedBox(height: AppSpacing.x2),
            _ActionRow(
              icon: Icons.person_outline_rounded,
              title: 'Profile',
              subtitle: 'Inspector name and local device identity',
              onTap: () => showGlassBottomSheet<void>(
                context,
                builder: (_) => const ProfileSheet(),
              ),
            ),
            _ActionRow(
              icon: Icons.tune_rounded,
              title: 'Settings',
              subtitle: 'Appearance and server connection',
              onTap: () => showGlassBottomSheet<void>(
                context,
                builder: (_) => SettingsSheet(
                  onFetchLatest: onFetchLatest,
                  onSync: onSync,
                ),
              ),
            ),
            _ActionRow(
              icon: Icons.cloud_download_outlined,
              title: 'Fetch latest data',
              subtitle: busy
                  ? 'Downloading from PostgreSQL...'
                  : 'Refresh station data now',
              onTap: busy ? null : onFetchLatest,
            ),
            _ActionRow(
              icon: Icons.cloud_upload_outlined,
              title: 'Sync inspection work',
              subtitle: 'Upload pending notes, photos and inspections',
              onTap: busy ? null : onSync,
            ),
          ],
        ),
      ),
    );
  }
}

class SettingsSheet extends ConsumerWidget {
  const SettingsSheet(
      {required this.onFetchLatest, required this.onSync, super.key});

  final VoidCallback onFetchLatest;
  final VoidCallback onSync;

  Future<void> _refreshCatering(
    BuildContext context,
    WidgetRef ref,
  ) async {
    final confirmed = await showAppConfirmation(
      context,
      title: 'Refresh catering data?',
      subtitle:
          'This imports the latest units and earnings from the configured Google Sheet into PostgreSQL, then replaces the offline station snapshot on this device.',
      confirmLabel: 'Refresh',
    );
    if (!confirmed || !context.mounted) return;

    try {
      final result = await ref
          .read(syncControllerProvider.notifier)
          .refreshCateringFromGoogleSheet();
      if (!context.mounted) return;
      showAppNotice(
        context,
        kind: AppNoticeKind.success,
        message:
            '${result.units} units and ${result.uniqueEarnings} receipts refreshed. ${result.duplicatesRemoved} duplicate rows removed.',
      );
    } catch (error) {
      if (!context.mounted) return;
      showAppNotice(
        context,
        kind: AppNoticeKind.error,
        message: '$error',
      );
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(syncControllerProvider);
    final busy = state.isLoading || state.asData?.value.busy == true;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
            AppSpacing.page, AppSpacing.x2, AppSpacing.page, AppSpacing.x3),
        child: ListView(
          shrinkWrap: true,
          children: [
            const PageHeading(
                title: 'Settings',
                subtitle: 'Control the app and its data connection.'),
            const SizedBox(height: AppSpacing.x2),
            GlassPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Data connection',
                      style: TextStyle(fontWeight: FontWeight.w900)),
                  const SizedBox(height: 6),
                  Text(AppConfig.apiBaseUrl,
                      style: Theme.of(context).textTheme.bodySmall),
                  const SizedBox(height: AppSpacing.x2),
                  Text(state.asData?.value.message ?? 'Ready'),
                  if (state.asData?.value.lastSyncAt != null)
                    Text(
                        'Last refresh ${shortDate(state.asData!.value.lastSyncAt)}'),
                  const SizedBox(height: AppSpacing.x2),
                  AppButton(
                    expand: true,
                    loading: busy,
                    onPressed: busy ? null : onFetchLatest,
                    icon: Icons.cloud_download_rounded,
                    label: 'Fetch latest from PostgreSQL',
                  ),
                  const SizedBox(height: AppSpacing.x1),
                  AppButton(
                    expand: true,
                    kind: AppButtonKind.secondary,
                    loading: busy,
                    onPressed:
                        busy ? null : () => _refreshCatering(context, ref),
                    icon: Icons.restaurant_menu_rounded,
                    label: 'Refresh catering from Google Sheet',
                  ),
                  if (state.asData?.value.lastCateringSyncAt != null) ...[
                    const SizedBox(height: 6),
                    Text(
                      'Last catering refresh ${shortDate(state.asData!.value.lastCateringSyncAt)}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                  const SizedBox(height: AppSpacing.x1),
                  AppButton(
                    expand: true,
                    kind: AppButtonKind.secondary,
                    loading: busy,
                    onPressed: busy ? null : onSync,
                    icon: Icons.cloud_upload_rounded,
                    label: 'Upload pending inspection work',
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.x2),
            const GlassPanel(
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Appearance',
                            style: TextStyle(fontWeight: FontWeight.w900)),
                        SizedBox(height: 4),
                        Text('Choose the Rail Inspect visual theme.'),
                      ],
                    ),
                  ),
                  ThemePickerButton(),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class ProfileSheet extends ConsumerStatefulWidget {
  const ProfileSheet({super.key});

  @override
  ConsumerState<ProfileSheet> createState() => _ProfileSheetState();
}

class _ProfileSheetState extends ConsumerState<ProfileSheet> {
  late final TextEditingController _name;
  var _loading = true;
  var _saving = false;

  @override
  void initState() {
    super.initState();
    _name = TextEditingController();
    _load();
  }

  Future<void> _load() async {
    final value = await ref.read(databaseProvider).metadata('profile_name');
    if (!mounted) return;
    _name.text = value ?? '';
    setState(() => _loading = false);
  }

  Future<void> _save() async {
    final value = _name.text.trim();
    if (value.isEmpty) return;
    setState(() => _saving = true);
    await ref.read(databaseProvider).setMetadata('profile_name', value);
    if (!mounted) return;
    setState(() => _saving = false);
    Navigator.pop(context);
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
            AppSpacing.page, AppSpacing.x2, AppSpacing.page, AppSpacing.x3),
        child: _loading
            ? const GlassLoadingList(itemCount: 2)
            : ListView(
                shrinkWrap: true,
                children: [
                  const PageHeading(
                      title: 'Profile',
                      subtitle: 'This name is used on this device.'),
                  const SizedBox(height: AppSpacing.x2),
                  Center(
                    child: CircleAvatar(
                      radius: 38,
                      backgroundColor: const Color(0xFFDCEBFF),
                      child: Icon(Icons.person_rounded,
                          size: 44,
                          color: Theme.of(context).colorScheme.primary),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.x2),
                  TextField(
                    controller: _name,
                    textCapitalization: TextCapitalization.words,
                    decoration: const InputDecoration(
                      labelText: 'Inspector name',
                      prefixIcon: Icon(Icons.badge_outlined),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.x2),
                  AppButton(
                    expand: true,
                    loading: _saving,
                    onPressed: _saving ? null : _save,
                    icon: Icons.save_outlined,
                    label: 'Save profile',
                  ),
                ],
              ),
      ),
    );
  }
}

class _ActionRow extends StatelessWidget {
  const _ActionRow(
      {required this.icon,
      required this.title,
      required this.subtitle,
      required this.onTap});

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(vertical: 3),
      leading: Container(
        width: 42,
        height: 42,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(14),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.08),
              blurRadius: 12,
              offset: const Offset(2, 4),
            ),
          ],
        ),
        child: Icon(icon, color: Theme.of(context).colorScheme.primary),
      ),
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
      subtitle: Text(subtitle),
      trailing: const Icon(Icons.chevron_right_rounded),
      onTap: onTap,
    );
  }
}
