import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite/sqflite.dart';

import '../../core/config.dart';
import '../../data/local/app_database.dart';
import '../../shared/widgets.dart';

class InspectionFieldLog extends StatelessWidget {
  const InspectionFieldLog({
    required this.evidence,
    required this.notes,
    super.key,
  });

  final List<Map<String, dynamic>> evidence;
  final List<Map<String, dynamic>> notes;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Field log',
                    style: Theme.of(context)
                        .textTheme
                        .headlineSmall
                        ?.copyWith(fontWeight: FontWeight.w900),
                  ),
                ),
                StatusBadge('${evidence.length} photos'),
                const SizedBox(width: 6),
                StatusBadge('${notes.length} notes'),
                AppIconButton(
                  tooltip: 'Close',
                  onPressed: () => Navigator.pop(context),
                  icon: Icons.close_rounded,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Expanded(
              child: evidence.isEmpty && notes.isEmpty
                  ? const EmptyState(
                      icon: Icons.collections_bookmark_outlined,
                      title: 'No field records yet',
                      message:
                          'Photos and quick notes recorded during this inspection appear here.',
                    )
                  : ListView(
                      children: [
                        if (evidence.isNotEmpty) ...[
                          const _LogHeading(
                            icon: Icons.photo_library_outlined,
                            label: 'Photo evidence',
                          ),
                          const SizedBox(height: 8),
                          GridView.builder(
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            itemCount: evidence.length,
                            gridDelegate:
                                const SliverGridDelegateWithFixedCrossAxisCount(
                              crossAxisCount: 2,
                              crossAxisSpacing: 10,
                              mainAxisSpacing: 10,
                              childAspectRatio: 0.82,
                            ),
                            itemBuilder: (context, index) =>
                                _EvidenceTile(row: evidence[index]),
                          ),
                        ],
                        if (notes.isNotEmpty) ...[
                          const SizedBox(height: 18),
                          const _LogHeading(
                            icon: Icons.sticky_note_2_outlined,
                            label: 'Inspection notes',
                          ),
                          const SizedBox(height: 8),
                          for (final note in notes)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 9),
                              child: GlassPanel(
                                padding: const EdgeInsets.all(13),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      '${note['title']}',
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w900,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text('${note['body']}'),
                                    if ('${note['context'] ?? ''}'
                                        .trim()
                                        .isNotEmpty) ...[
                                      const SizedBox(height: 7),
                                      Text(
                                        '${note['context']}',
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodySmall,
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                            ),
                        ],
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class InspectionFieldActions {
  static Future<int> recoverLostEvidence({
    required AppDatabase database,
    required String inspectionId,
  }) async {
    final lost = await ImagePicker().retrieveLostData();
    final files = lost.files ?? const <XFile>[];
    var recovered = 0;
    for (final photo in files) {
      final root = await getDatabasesPath();
      final directory = Directory(path.join(root, 'inspection_evidence'));
      await directory.create(recursive: true);
      final extension = path.extension(photo.path).toLowerCase();
      final saved = await File(photo.path).copy(
        path.join(
          directory.path,
          '${DateTime.now().microsecondsSinceEpoch}_recovered$extension',
        ),
      );
      await database.addEvidence(
        inspectionId: inspectionId,
        localPath: saved.path,
        mimeType: extension == '.png' ? 'image/png' : 'image/jpeg',
        caption: 'Recovered inspection photo',
        context: 'Recovered after camera interruption',
      );
      recovered++;
    }
    return recovered;
  }

  static Future<bool> captureEvidence({
    required BuildContext context,
    required AppDatabase database,
    required String inspectionId,
    String? responseId,
    String? questionCode,
    String? defaultContext,
  }) async {
    final source = await showGlassBottomSheet<ImageSource>(
      context,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.page,
            AppSpacing.x1,
            AppSpacing.page,
            AppSpacing.x3,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SectionTitle(
                title: 'Add photo evidence',
                subtitle: 'Take a new photo or select one already saved.',
              ),
              const SizedBox(height: AppSpacing.x3),
              Row(
                children: [
                  Expanded(
                    child: SoftActionButton(
                      icon: Icons.photo_camera_outlined,
                      label: 'Camera',
                      onPressed: () =>
                          Navigator.pop(context, ImageSource.camera),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.x1),
                  Expanded(
                    child: SoftActionButton(
                      icon: Icons.photo_library_outlined,
                      label: 'Gallery',
                      onPressed: () =>
                          Navigator.pop(context, ImageSource.gallery),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
    if (source == null) return false;
    XFile? photo;
    try {
      photo = await ImagePicker().pickImage(
        source: source,
        imageQuality: 72,
        maxWidth: 1600,
      );
    } catch (_) {
      if (context.mounted) {
        showAppNotice(
          context,
          message:
              'Camera or photo access is unavailable. Check app permissions.',
          kind: AppNoticeKind.error,
        );
      }
      return false;
    }
    if (photo == null || !context.mounted) return false;
    final details = await showDialog<_EvidenceDetails>(
      context: context,
      builder: (_) => _EvidenceDialog(defaultContext: defaultContext),
    );
    if (details == null) return false;
    try {
      final root = await getDatabasesPath();
      final directory = Directory(path.join(root, 'inspection_evidence'));
      await directory.create(recursive: true);
      final extension = path.extension(photo.path).toLowerCase();
      final saved = await File(photo.path).copy(
        path.join(
          directory.path,
          '${DateTime.now().microsecondsSinceEpoch}$extension',
        ),
      );
      await database.addEvidence(
        inspectionId: inspectionId,
        responseId: responseId,
        questionCode: questionCode,
        localPath: saved.path,
        mimeType: extension == '.png' ? 'image/png' : 'image/jpeg',
        caption: details.caption,
        context: details.context,
      );
    } catch (_) {
      if (context.mounted) {
        showAppNotice(
          context,
          message: 'The photo could not be saved. Please try again.',
          kind: AppNoticeKind.error,
        );
      }
      return false;
    }
    return true;
  }

  static Future<bool> addNote({
    required BuildContext context,
    required AppDatabase database,
    required String inspectionId,
    String? sectionCode,
    String? questionCode,
    String? defaultContext,
  }) async {
    final detail = await showDialog<_NoteDetails>(
      context: context,
      builder: (_) => _NoteDialog(defaultContext: defaultContext),
    );
    if (detail == null) return false;
    await database.addInspectionNote(
      inspectionId: inspectionId,
      sectionCode: sectionCode,
      questionCode: questionCode,
      title: detail.title,
      body: detail.body,
      context: detail.context,
    );
    return true;
  }
}

class _EvidenceTile extends StatelessWidget {
  const _EvidenceTile({required this.row});

  final Map<String, dynamic> row;

  @override
  Widget build(BuildContext context) {
    final localPath = '${row['local_path'] ?? ''}';
    final file = File(localPath);
    final exists = localPath.isNotEmpty && file.existsSync();
    return GlassPanel(
      semanticLabel:
          'View ${displayText(row['caption'], fallback: 'inspection photo')}',
      onTap: () => showDialog<void>(
        context: context,
        builder: (_) => AppDialogShell(
          icon: Icons.photo_outlined,
          title: displayText(row['caption'], fallback: 'Inspection photo'),
          subtitle: displayText(
            row['context'],
            fallback: 'Photo evidence attached to this inspection.',
          ),
          content: ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.control),
            child: AspectRatio(
              aspectRatio: 4 / 3,
              child: exists
                  ? Image.file(file, fit: BoxFit.contain)
                  : Image.network(
                      '${AppConfig.apiBaseUrl}/api/mobile/v1/evidence/'
                      '${row['evidence_id']}/content',
                      fit: BoxFit.contain,
                    ),
            ),
          ),
          actions: [
            AppButton(
              label: 'Close',
              kind: AppButtonKind.ghost,
              onPressed: () => Navigator.pop(context),
            ),
          ],
        ),
      ),
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: SizedBox(
              width: double.infinity,
              child: exists
                  ? Image.file(file, fit: BoxFit.cover)
                  : Image.network(
                      '${AppConfig.apiBaseUrl}/api/mobile/v1/evidence/'
                      '${row['evidence_id']}/content',
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => const ColoredBox(
                        color: Color(0x14006B64),
                        child: Icon(Icons.cloud_off_outlined, size: 36),
                      ),
                    ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(10),
            child: Text(
              displayText(row['caption'], fallback: 'Inspection photo'),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
        ],
      ),
    );
  }
}

class _LogHeading extends StatelessWidget {
  const _LogHeading({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: Theme.of(context).colorScheme.primary),
        const SizedBox(width: 8),
        Text(
          label,
          style: Theme.of(
            context,
          ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
        ),
      ],
    );
  }
}

class _EvidenceDetails {
  const _EvidenceDetails(this.caption, this.context);
  final String? caption;
  final String? context;
}

class _EvidenceDialog extends StatefulWidget {
  const _EvidenceDialog({this.defaultContext});
  final String? defaultContext;

  @override
  State<_EvidenceDialog> createState() => _EvidenceDialogState();
}

class _EvidenceDialogState extends State<_EvidenceDialog> {
  final _caption = TextEditingController();
  late final TextEditingController _context;

  @override
  void initState() {
    super.initState();
    _context = TextEditingController(text: widget.defaultContext ?? '');
  }

  @override
  void dispose() {
    _caption.dispose();
    _context.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppDialogShell(
      icon: Icons.add_a_photo_outlined,
      title: 'Photo details',
      subtitle: 'Add a short caption so this evidence is useful later.',
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _caption,
            autofocus: true,
            decoration: const InputDecoration(
              labelText: 'What does this photo show?',
              prefixIcon: Icon(Icons.short_text_rounded),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _context,
            decoration: const InputDecoration(
              labelText: 'Location or context',
              prefixIcon: Icon(Icons.place_outlined),
            ),
          ),
        ],
      ),
      actions: [
        AppButton(
          label: 'Cancel',
          kind: AppButtonKind.ghost,
          onPressed: () => Navigator.pop(context),
        ),
        AppButton(
          label: 'Attach photo',
          icon: Icons.attachment_rounded,
          onPressed: () => Navigator.pop(
            context,
            _EvidenceDetails(
              _nullable(_caption.text),
              _nullable(_context.text),
            ),
          ),
        ),
      ],
    );
  }
}

class _NoteDetails {
  const _NoteDetails(this.title, this.body, this.context);
  final String title;
  final String body;
  final String? context;
}

class _NoteDialog extends StatefulWidget {
  const _NoteDialog({this.defaultContext});
  final String? defaultContext;

  @override
  State<_NoteDialog> createState() => _NoteDialogState();
}

class _NoteDialogState extends State<_NoteDialog> {
  final _title = TextEditingController();
  final _body = TextEditingController();
  late final TextEditingController _context;

  @override
  void initState() {
    super.initState();
    _context = TextEditingController(text: widget.defaultContext ?? '');
  }

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    _context.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppDialogShell(
      icon: Icons.sticky_note_2_outlined,
      title: 'Inspection note',
      subtitle: 'Record concise context while you are at the location.',
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _title,
              autofocus: true,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(labelText: 'Short title'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _body,
              minLines: 3,
              maxLines: 7,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(
                labelText: 'Observation or note',
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _context,
              decoration: const InputDecoration(
                labelText: 'Location or context',
                prefixIcon: Icon(Icons.place_outlined),
              ),
            ),
          ],
        ),
      ),
      actions: [
        AppButton(
          label: 'Cancel',
          kind: AppButtonKind.ghost,
          onPressed: () => Navigator.pop(context),
        ),
        AppButton(
          label: 'Save note',
          icon: Icons.save_outlined,
          onPressed: _title.text.trim().isEmpty || _body.text.trim().isEmpty
              ? null
              : () => Navigator.pop(
                    context,
                    _NoteDetails(
                      _title.text.trim(),
                      _body.text.trim(),
                      _nullable(_context.text),
                    ),
                  ),
        ),
      ],
    );
  }
}

String? _nullable(String value) {
  final trimmed = value.trim();
  return trimmed.isEmpty ? null : trimmed;
}
