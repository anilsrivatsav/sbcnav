import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/remote/mobile_api.dart';
import '../../shared/widgets.dart';
import '../reports/report_pdf_export.dart';
import 'contract_filters.dart';

class ContractsScreen extends ConsumerStatefulWidget {
  const ContractsScreen({super.key});

  @override
  ConsumerState<ContractsScreen> createState() => _ContractsScreenState();
}

class _ContractsScreenState extends ConsumerState<ContractsScreen> {
  String _family = 'publicity';
  String _publicityStatus = 'running';
  String _policy = 'all';
  String _asset = 'all';
  String _cateringView = 'active';
  String _type = 'all';
  String _station = 'all';
  String _query = '';
  final _searchController = TextEditingController();
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<Map<String, dynamic>> _load() async {
    final api = ref.read(mobileApiProvider);
    final results = await Future.wait([
      api.contracts(status: 'all'),
      api.dashboardBootstrap(),
    ]);
    final publicity = results[0];
    final dashboard = results[1];
    return {
      'publicity': publicity['items'] as List? ?? const [],
      'units': (dashboard['units'] as Map?)?['items'] as List? ?? const [],
    };
  }

  void _refresh() => setState(() => _future = _load());

  void _resetFilters() {
    setState(() {
      _query = '';
      _searchController.clear();
      if (_family == 'publicity') {
        _publicityStatus = 'running';
        _policy = 'all';
        _asset = 'all';
      } else {
        _cateringView = 'active';
        _type = 'all';
        _station = 'all';
      }
    });
  }

  Future<void> _exportPdf(List<Map<dynamic, dynamic>> rows) async {
    await exportContractsPdf(
      rows: rows.map((row) => Map<String, dynamic>.from(row)).toList(),
      family: _family,
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const GlassLoadingList(itemCount: 6);
        }
        if (snapshot.hasError) {
          return ErrorPane(error: snapshot.error!, retry: _refresh);
        }

        final publicity = (snapshot.data?['publicity'] as List? ?? const [])
            .whereType<Map>()
            .toList(growable: false);
        final units = (snapshot.data?['units'] as List? ?? const [])
            .whereType<Map>()
            .toList(growable: false);
        final policies = publicity
            .map((row) => '${row['policy_code'] ?? ''}'.trim())
            .where((value) => value.isNotEmpty)
            .toSet()
            .toList()
          ..sort();
        final assets = publicity.expand(contractAssetLabels).toSet().toList()
          ..sort();
        final types = units
            .map((row) => '${row['type_of_unit'] ?? ''}'.trim())
            .where((value) => value.isNotEmpty)
            .toSet()
            .toList()
          ..sort();
        final stations = units
            .map((row) => '${row['station_code'] ?? ''}'
                .trim()
                .replaceFirst(RegExp(r'\.0$'), ''))
            .where((value) => value.isNotEmpty)
            .toSet()
            .toList()
          ..sort();

        final publicityRows = filterPublicityContracts(publicity,
            status: _publicityStatus,
            policy: _policy,
            asset: _asset,
            query: _query);
        final cateringRows = filterCateringContracts(units,
            view: _cateringView, type: _type, station: _station, query: _query);
        final rows = _family == 'publicity' ? publicityRows : cateringRows;

        return RefreshIndicator(
          onRefresh: () async => _refresh(),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(18, 20, 18, 32),
            children: [
              Row(children: [
                Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      Text('Contracts',
                          style: Theme.of(context)
                              .textTheme
                              .headlineMedium
                              ?.copyWith(fontWeight: FontWeight.w800)),
                      const SizedBox(height: 4),
                      Text('Catering and publicity contracts from PostgreSQL',
                          style: Theme.of(context).textTheme.bodyMedium),
                    ])),
                IconButton.filledTonal(
                    tooltip: 'Refresh PostgreSQL data',
                    onPressed: _refresh,
                    icon: const Icon(Icons.refresh_rounded)),
              ]),
              const SizedBox(height: 14),
              SegmentedButton<String>(
                segments: [
                  ButtonSegment(
                      value: 'publicity',
                      icon: const Icon(Icons.campaign_outlined),
                      label: Text('Publicity (${publicity.length})')),
                  ButtonSegment(
                      value: 'catering',
                      icon: const Icon(Icons.restaurant_outlined),
                      label: Text('Catering (${units.length})')),
                ],
                selected: {_family},
                onSelectionChanged: (value) => setState(() {
                  _family = value.first;
                  _query = '';
                  _searchController.clear();
                }),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: _searchController,
                textInputAction: TextInputAction.search,
                decoration: InputDecoration(
                  labelText: 'Search contracts',
                  prefixIcon: const Icon(Icons.search_rounded),
                  suffixIcon: _query.isEmpty
                      ? null
                      : IconButton(
                          tooltip: 'Clear search',
                          onPressed: () => setState(() {
                                _query = '';
                                _searchController.clear();
                              }),
                          icon: const Icon(Icons.close_rounded)),
                ),
                onChanged: (value) => setState(() => _query = value),
              ),
              const SizedBox(height: 12),
              GlassPanel(
                padding: const EdgeInsets.all(14),
                child: _family == 'publicity'
                    ? _PublicityFilters(
                        rows: publicity,
                        policies: policies,
                        assets: assets,
                        status: _publicityStatus,
                        policy: _policy,
                        asset: _asset,
                        onStatusChanged: (value) => setState(() {
                          _publicityStatus = value;
                          _policy = 'all';
                          _asset = 'all';
                        }),
                        onPolicyChanged: (value) => setState(() {
                          _policy = value;
                          _asset = 'all';
                        }),
                        onAssetChanged: (value) =>
                            setState(() => _asset = value),
                      )
                    : _CateringFilters(
                        rows: units,
                        types: types,
                        stations: stations,
                        view: _cateringView,
                        type: _type,
                        station: _station,
                        onViewChanged: (value) => setState(() {
                          _cateringView = value;
                          _type = 'all';
                          _station = 'all';
                        }),
                        onTypeChanged: (value) => setState(() {
                          _type = value;
                          _station = 'all';
                        }),
                        onStationChanged: (value) =>
                            setState(() => _station = value),
                      ),
              ),
              const SizedBox(height: 10),
              Row(children: [
                Expanded(
                    child: Text(
                        '${rows.length} matching ${_family == 'publicity' ? 'contracts' : 'records'}',
                        style: Theme.of(context)
                            .textTheme
                            .titleSmall
                            ?.copyWith(fontWeight: FontWeight.w800))),
                TextButton.icon(
                    onPressed: _resetFilters,
                    icon: const Icon(Icons.filter_alt_off_rounded),
                    label: const Text('Reset')),
                TextButton.icon(
                    onPressed: rows.isEmpty ? null : () => _exportPdf(rows),
                    icon: const Icon(Icons.picture_as_pdf_rounded),
                    label: const Text('PDF')),
              ]),
              const SizedBox(height: 6),
              if (rows.isEmpty)
                const EmptyState(
                    icon: Icons.assignment_outlined,
                    title: 'No contracts',
                    message: 'No contracts match the selected filters.'),
              if (_family == 'publicity')
                for (final row in publicityRows)
                  _PublicityContractCard(row: row)
              else
                for (final row in cateringRows) _CateringContractCard(row: row),
            ],
          ),
        );
      },
    );
  }
}

class _PublicityFilters extends StatelessWidget {
  const _PublicityFilters(
      {required this.rows,
      required this.policies,
      required this.assets,
      required this.status,
      required this.policy,
      required this.asset,
      required this.onStatusChanged,
      required this.onPolicyChanged,
      required this.onAssetChanged});
  final List<Map<dynamic, dynamic>> rows;
  final List<String> policies;
  final List<String> assets;
  final String status;
  final String policy;
  final String asset;
  final ValueChanged<String> onStatusChanged;
  final ValueChanged<String> onPolicyChanged;
  final ValueChanged<String> onAssetChanged;

  int _statusCount(String value) =>
      filterPublicityContracts(rows, status: value).length;
  int _policyCount(String value) =>
      filterPublicityContracts(rows, status: status, policy: value).length;
  int _assetCount(String value) => filterPublicityContracts(rows,
          status: status, policy: policy, asset: value)
      .length;

  @override
  Widget build(BuildContext context) => Column(children: [
        DropdownButtonFormField<String>(
          key: ValueKey('publicity-status-$status'),
          initialValue: status,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Status'),
          items: ['running', 'completed', 'cancelled', 'all']
              .map((value) => DropdownMenuItem(
                  value: value,
                  child: Text(
                      '${_title(value == 'all' ? 'All contracts' : value)} (${_statusCount(value)})')))
              .toList(),
          onChanged: (value) => onStatusChanged(value ?? 'running'),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          key: ValueKey('publicity-policy-$policy'),
          initialValue: policy,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Policy'),
          items: [
            DropdownMenuItem(
                value: 'all',
                child: Text('All policies (${_policyCount('all')})')),
            ...policies.map((value) => DropdownMenuItem(
                value: value, child: Text('$value (${_policyCount(value)})'))),
          ],
          onChanged: (value) => onPolicyChanged(value ?? 'all'),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          key: ValueKey('publicity-asset-$asset'),
          initialValue: asset,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Station / asset'),
          items: [
            DropdownMenuItem(
                value: 'all',
                child: Text('All stations / assets (${_assetCount('all')})')),
            ...assets.map((value) => DropdownMenuItem(
                value: value,
                child: Text('$value (${_assetCount(value)})',
                    overflow: TextOverflow.ellipsis))),
          ],
          onChanged: (value) => onAssetChanged(value ?? 'all'),
        ),
      ]);
}

class _CateringFilters extends StatelessWidget {
  const _CateringFilters(
      {required this.rows,
      required this.types,
      required this.stations,
      required this.view,
      required this.type,
      required this.station,
      required this.onViewChanged,
      required this.onTypeChanged,
      required this.onStationChanged});
  final List<Map<dynamic, dynamic>> rows;
  final List<String> types;
  final List<String> stations;
  final String view;
  final String type;
  final String station;
  final ValueChanged<String> onViewChanged;
  final ValueChanged<String> onTypeChanged;
  final ValueChanged<String> onStationChanged;

  int _count(
          {String? selectedView,
          String? selectedType,
          String? selectedStation}) =>
      filterCateringContracts(rows,
              view: selectedView ?? view,
              type: selectedType ?? type,
              station: selectedStation ?? station)
          .length;

  @override
  Widget build(BuildContext context) => Column(children: [
        DropdownButtonFormField<String>(
          key: ValueKey('catering-view-$view'),
          initialValue: view,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'View'),
          items: [
            DropdownMenuItem(
                value: 'active',
                child: Text(
                    'Running / active (${_count(selectedView: 'active', selectedType: 'all', selectedStation: 'all')})')),
            DropdownMenuItem(
                value: 'other',
                child: Text(
                    'Other / unawarded (${_count(selectedView: 'other', selectedType: 'all', selectedStation: 'all')})')),
          ],
          onChanged: (value) => onViewChanged(value ?? 'active'),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          key: ValueKey('catering-type-$type'),
          initialValue: type,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Type'),
          items: [
            DropdownMenuItem(
                value: 'all',
                child: Text('All types (${_count(selectedType: 'all')})')),
            ...types.map((value) => DropdownMenuItem(
                value: value,
                child: Text('$value (${_count(selectedType: value)})',
                    overflow: TextOverflow.ellipsis))),
          ],
          onChanged: (value) => onTypeChanged(value ?? 'all'),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          key: ValueKey('catering-station-$station'),
          initialValue: station,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Station'),
          items: [
            DropdownMenuItem(
                value: 'all',
                child:
                    Text('All stations (${_count(selectedStation: 'all')})')),
            ...stations.map((value) => DropdownMenuItem(
                value: value,
                child: Text('$value (${_count(selectedStation: value)})'))),
          ],
          onChanged: (value) => onStationChanged(value ?? 'all'),
        ),
      ]);
}

class _PublicityContractCard extends StatelessWidget {
  const _PublicityContractCard({required this.row});
  final Map<dynamic, dynamic> row;

  @override
  Widget build(BuildContext context) {
    final period = row['period'] is Map ? row['period'] as Map : const {};
    final financials =
        row['financials'] is Map ? row['financials'] as Map : const {};
    final contractor =
        row['contractor'] is Map ? row['contractor'] as Map : const {};
    final assets = contractAssetLabels(row);
    return _ContractPanel(
      title: "${row['contract_name'] ?? 'Unnamed contract'}",
      subtitle:
          "${row['contract_number'] ?? 'No contract number'} · ${contractor['legal_name'] ?? 'No contractor'}",
      status: "${row['status'] ?? 'unknown'}",
      facts: [
        _Fact(
            icon: Icons.policy_outlined,
            value: "${row['policy_code'] ?? 'No policy'}"),
        _Fact(
            icon: Icons.place_outlined,
            value: assets.isEmpty ? 'Other asset' : assets.join(', ')),
        _Fact(
            icon: Icons.calendar_today_outlined,
            value: "${period['start'] ?? '—'} → ${period['end'] ?? '—'}"),
        _Fact(
            icon: Icons.currency_rupee,
            value: "₹${financials['total_contract_value'] ?? 0}"),
      ],
    );
  }
}

class _CateringContractCard extends StatelessWidget {
  const _CateringContractCard({required this.row});
  final Map<dynamic, dynamic> row;

  @override
  Widget build(BuildContext context) => _ContractPanel(
        title:
            "${row['unit_no'] ?? 'Unnamed unit'} · ${row['type_of_unit'] ?? 'Catering'}",
        subtitle: "${row['licensee_name'] ?? 'No licensee'}",
        status:
            "${row['unit_status'] ?? (isAvailableCateringUnit(row) ? 'Available' : 'Unknown')}",
        facts: [
          _Fact(
              icon: Icons.place_outlined,
              value: "${row['station_code'] ?? 'No station'}"),
          _Fact(
              icon: Icons.storefront_outlined,
              value: "${row['type_of_unit'] ?? 'Type not recorded'}"),
          _Fact(
              icon: Icons.calendar_today_outlined,
              value:
                  "${row['contract_from'] ?? '—'} → ${row['contract_to'] ?? '—'}"),
          _Fact(
              icon: Icons.currency_rupee, value: "₹${row['license_fee'] ?? 0}"),
        ],
      );
}

class _ContractPanel extends StatelessWidget {
  const _ContractPanel(
      {required this.title,
      required this.subtitle,
      required this.status,
      required this.facts});
  final String title;
  final String subtitle;
  final String status;
  final List<Widget> facts;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: GlassPanel(
          padding: const EdgeInsets.all(16),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(
                  child: Text(title,
                      style: Theme.of(context)
                          .textTheme
                          .titleMedium
                          ?.copyWith(fontWeight: FontWeight.w800))),
              const SizedBox(width: 8),
              _StatusPill(status),
            ]),
            const SizedBox(height: 5),
            Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 12),
            Wrap(spacing: 8, runSpacing: 8, children: facts),
          ]),
        ),
      );
}

class _Fact extends StatelessWidget {
  const _Fact({required this.icon, required this.value});
  final IconData icon;
  final String value;

  @override
  Widget build(BuildContext context) => Chip(
        avatar: Icon(icon, size: 15),
        label: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 260),
            child: Text(value, overflow: TextOverflow.ellipsis)),
      );
}

class _StatusPill extends StatelessWidget {
  const _StatusPill(this.value);
  final String value;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
        decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.primaryContainer,
            borderRadius: BorderRadius.circular(20)),
        child: Text(value,
            style: Theme.of(context)
                .textTheme
                .labelSmall
                ?.copyWith(fontWeight: FontWeight.w800)),
      );
}

String _title(String value) =>
    value.isEmpty ? value : '${value[0].toUpperCase()}${value.substring(1)}';
