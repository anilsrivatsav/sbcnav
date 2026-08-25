import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/remote/mobile_api.dart';
import '../../shared/widgets.dart';

class ContractsScreen extends ConsumerStatefulWidget {
  const ContractsScreen({super.key});

  @override
  ConsumerState<ContractsScreen> createState() => _ContractsScreenState();
}

class _ContractsScreenState extends ConsumerState<ContractsScreen> {
  String _status = 'running';
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<Map<String, dynamic>> _load() => ref.read(mobileApiProvider).contracts(status: _status);

  void _changeStatus(String value) => setState(() {
        _status = value;
        _future = _load();
      });

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) return const GlassLoadingList(itemCount: 6);
        if (snapshot.hasError) return ErrorPane(error: snapshot.error!, retry: () => setState(() => _future = _load()));
        final rows = (snapshot.data?['items'] as List? ?? const []).whereType<Map>().toList();
        return RefreshIndicator(
          onRefresh: () async => setState(() => _future = _load()),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(18, 20, 18, 32),
            children: [
              Text('Contracts', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: 6),
              Text('Awarded, running, completed and cancelled contracts', style: Theme.of(context).textTheme.bodyMedium),
              const SizedBox(height: 18),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(children: [for (final value in const ['all', 'awarded', 'running', 'completed', 'cancelled']) Padding(padding: const EdgeInsets.only(right: 8), child: ChoiceChip(label: Text(value[0].toUpperCase() + value.substring(1)), selected: _status == value, onSelected: (_) => _changeStatus(value)))]),
              ),
              const SizedBox(height: 18),
              if (rows.isEmpty) const EmptyState(icon: Icons.assignment_outlined, title: 'No contracts', message: 'No contracts match this status.'),
              for (final row in rows) _ContractCard(row: row),
            ],
          ),
        );
      },
    );
  }
}

class _ContractCard extends StatelessWidget {
  const _ContractCard({required this.row});
  final Map row;

  @override
  Widget build(BuildContext context) {
    final period = row['period'] is Map ? row['period'] as Map : const {};
    final financials = row['financials'] is Map ? row['financials'] as Map : const {};
    final contractor = row['contractor'] is Map ? row['contractor'] as Map : const {};
    final assets = row['assets'] is List ? row['assets'] as List : const [];
    final asset = assets.isNotEmpty && assets.first is Map ? assets.first as Map : const {};
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: GlassPanel(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: Text('${row['contract_name'] ?? 'Unnamed contract'}', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800))), _StatusPill('${row['status'] ?? 'unknown']}')]),
          const SizedBox(height: 5),
          Text('${row['contract_number'] ?? 'No contract number'} · ${contractor['legal_name'] ?? 'No contractor'}', style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: [
            _Fact(icon: Icons.policy_outlined, value: '${row['policy_code'] ?? 'No policy'}'),
            _Fact(icon: Icons.place_outlined, value: '${asset['station_code'] ?? asset['train_number'] ?? asset['asset_name'] ?? 'Other asset'}'),
            _Fact(icon: Icons.calendar_today_outlined, value: '${period['start'] ?? '—'} → ${period['end'] ?? '—'}'),
            _Fact(icon: Icons.currency_rupee, value: '₹${financials['total_contract_value'] ?? 0}'),
          ]),
        ]),
      ),
    );
  }
}

class _Fact extends StatelessWidget {
  const _Fact({required this.icon, required this.value});
  final IconData icon;
  final String value;
  @override
  Widget build(BuildContext context) => Chip(avatar: Icon(icon, size: 15), label: Text(value, overflow: TextOverflow.ellipsis));
}

class _StatusPill extends StatelessWidget {
  const _StatusPill(this.value);
  final String value;
  @override
  Widget build(BuildContext context) => Container(padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5), decoration: BoxDecoration(color: Theme.of(context).colorScheme.primaryContainer, borderRadius: BorderRadius.circular(20)), child: Text(value, style: Theme.of(context).textTheme.labelSmall?.copyWith(fontWeight: FontWeight.w800)));
}
