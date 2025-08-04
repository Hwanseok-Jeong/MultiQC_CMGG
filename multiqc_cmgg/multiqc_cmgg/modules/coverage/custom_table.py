def create(
        data: Dict[SectionKey, SectionT],
        table_id: str,
        table_anchor: Anchor,
        pconfig: TableConfig,
        headers: Dict[SectionKey, Dict[ColumnKey, ColumnDict]],
    ) -> "DataTable":
    """Prepare data for use in a table or plot"""
    # Violin plot's PConfig does this for the plot ID. We also do that second turn time for
    # the table anchor because that's the ID that is shown in the Configure Columns modal
    if table_anchor in config.custom_plot_config:
        for k, v in config.custom_plot_config[table_anchor].items():
            if isinstance(k, str) and k in pconfig.__dict__:
                setattr(pconfig, k, v)

    # Each section to have a list of groups (even if there is just one element in a group)
    input_section_key: SectionKey
    input_section: SectionT
    input_group: GroupT
    unified_sections__with_nulls: Dict[SectionKey, Dict[SampleGroup, List[InputRow]]] = {}
    for input_section_key, input_section in data.items():
        rows_by_group: Dict[SampleGroup, List[InputRow]] = {}
        for g_name, input_group in input_section.items():
            g_name = SampleGroup(str(g_name))  # Make sure sample names are strings

            # --- 여기에 sample name 분리 로직 추가 ---
            if "_" in str(g_name):
                sample_name = str(g_name).split("_")[0]
                g_name = SampleGroup(sample_name)

            if isinstance(input_group, dict):  # just one row, defined as a mapping from metric to value
                # Remove non-scalar values for table cells
                rows_by_group[g_name] = [InputRow(sample=SampleName(g_name), data=input_group)]
            elif isinstance(input_group, list):  # multiple rows, each defined as a mapping from metric to value
                rows_by_group[g_name] = input_group
            else:
                assert isinstance(input_group, InputRow)
                rows_by_group[g_name] = [input_group]

        # --- 빈 그룹 제거 ---
        rows_by_group = {k: v for k, v in rows_by_group.items() if v}
        unified_sections__with_nulls[input_section_key] = rows_by_group
    del data

    # Go through each table section and create a list of Section objects
    sections: Dict[SectionKey, TableSection] = {}
    for sec_idx, (section_key, rows_by_sname__with_nulls) in enumerate(unified_sections__with_nulls.items()):
        header_by_key: Union[Dict[ColumnKey, ColumnDict], Dict[str, ColumnDict]] = (
            headers.get(SectionKey(section_key)) or dict()
        )
        if not header_by_key:
            pconfig.only_defined_headers = False

        column_by_key: Dict[ColumnKey, ColumnMeta] = dict()
        col_dict_by_key_copy: Dict[ColumnKey, ColumnDict] = _get_or_create_headers(
            rows_by_sname__with_nulls, header_by_key, pconfig
        )
        for col_key, col_dict in col_dict_by_key_copy.items():
            column_by_key[col_key] = ColumnMeta.create(
                col_dict=col_dict, col_key=col_key, sec_idx=sec_idx, pconfig=pconfig, table_anchor=table_anchor
            )

        # Filter out null values and columns that are not present in column_by_key,
        # and apply "modify" and "format" to values. Will generate non-null data and str data.
        section = TableSection(column_by_key=column_by_key)
        for g_name, group_rows__with_nulls in rows_by_sname__with_nulls.items():
            for input_row in group_rows__with_nulls:
                row = Row(sample=input_row.sample)
                for col_key, optional_val in input_row.data.items():
                    if col_key not in column_by_key:  # missing in provided headers
                        continue
                    if optional_val is None or str(optional_val).strip() == "":  # empty
                        continue
                    val_obj = _process_and_format_value(
                        optional_val, column_by_key[col_key], parse_numeric=pconfig.parse_numeric
                    )
                    row.data[col_key] = val_obj
                if row.data:
                    section.rows_by_sgroup[g_name].append(row)

        # Remove empty groups:
        section.rows_by_sgroup = {sname: rows for sname, rows in section.rows_by_sgroup.items() if rows}

        # Work out max and min value if not given:
        for col_key, column in column_by_key.items():
            _determine_dmin_and_dmax(column, col_key, section.rows_by_sgroup)

        sections[section_key] = section

    del unified_sections__with_nulls

    shared_keys: Dict[str, Dict[str, Union[int, float]]] = _collect_shared_keys(sections)

    # Overwrite shared key settings and at the same time assign to buckets for sorting
    # So the final ordering is:
    #   placement > section > explicit_ordering
    # Of course, the user can shuffle these manually.
    headers_in_order: Dict[float, List[Tuple[int, ColumnKey]]] = defaultdict(list)
    for sec_idx, section in enumerate(sections.values()):
        for col_key, column in section.column_by_key.items():
            if column.shared_key is not None:
                column.dmax = shared_keys[column.shared_key].get("dmax")
                column.dmin = shared_keys[column.shared_key].get("dmin")

            headers_in_order[column.placement].append((sec_idx, col_key))

    # Remove callable headers that are not compatible with JSON
    for section in sections.values():
        for column in section.column_by_key.values():
            column.modify = None
            if not isinstance(column.format, str):
                column.format = None

    # Assign to class
    return DataTable(
        id=table_id,
        anchor=table_anchor,
        section_by_id=sections,
        headers_in_order=headers_in_order,
        pconfig=pconfig,
    )
