# IDS Rules for Energy Model Validation

This directory contains Information Delivery Specification (IDS) files for validating IFC models intended for energy analysis through gbXML conversion.

## Overview

These IDS files define 68 validation rules organized into 9 thematic categories. The rules ensure that an IFC model contains all necessary information for successful energy modeling and simulation.

**All files validated**: ✓ Each IDS file has been tested against the IDS 1.0 schema and sample IFC models.

## Quick Start

```bash
# Install ifctester (requires Python)
pip install ifctester

# Validate a single category
python -m ifctester IDS/01-spatial-structure.ids your-model.ifc

# Validate all energy model requirements
for ids in IDS/*.ids; do
    python -m ifctester "$ids" your-model.ifc
done
```

**Interpreting results:**
- ✓ **PASS**: Your IFC model meets the requirement
- ✗ **FAIL**: Your IFC model is missing required data or violates constraints
- Failures indicate what needs to be fixed in your model for proper energy analysis

## IDS Files

### 01-spatial-structure.ids
**Rules 1-9**: Validates the spatial hierarchy required for energy modeling.

- Site, Building, Storey, and Space existence
- Proper containment relationships (Site → Building → Storey → Space)
- Site location data (latitude, longitude, elevation, postal address)

### 02-space-properties.ids
**Rules 10-15**: Validates space properties required for energy calculations.

- Space area (NetFloorArea or NetPlannedArea)
- Space volume (NetVolume or GrossVolume)
- Space name, category/type, and conditioning status
- Space height (optional but recommended)

### 03-space-boundaries.ids
**Rules 16-23**: Validates 2nd level space boundaries (critical for energy modeling).

- Space boundaries exist for each space
- Boundaries are 2nd level (IFC4: IfcRelSpaceBoundary2ndLevel, IFC2X3: Name="2ndLevel")
- Boundaries have geometry, related elements, and relating spaces
- Valid boundary element types (walls, slabs, roofs, windows, doors, etc.)
- External/internal classification (InternalOrExternalBoundary attribute)
- IsExternal properties on boundary elements

### 04-materials-construction.ids
**Rules 24-30**: Validates material associations and construction assemblies.

- Material associations on boundary elements (walls, slabs, roofs, curtain walls)
- Material layer sets with names
- Material layers with materials and thicknesses
- Material names

### 05-thermal-properties.ids
**Rules 31-39**: Validates thermal properties for energy calculations.

- Element U-values (ThermalTransmittance) on walls, slabs, roofs
- Material R-values or thermal conductivity
- Material density and specific heat capacity (for thermal mass)
- Absorptance properties
- Valid value ranges (U: 0.1-6.0 W/m²K, R > 0)

### 06-windows-doors.ids
**Rules 40-50**: Validates window and door properties for glazing analysis.

- Type assignments (IsTypedBy)
- Parent boundaries via FillsVoids relationships (IFC2X3)
- U-values for windows and doors
- Glazing area fraction and visual light transmittance
- Solar heat gain coefficient (SHGC)
- Frame properties (thickness, conductivity)
- Glass layers and thickness
- Shading device type

**Note**: Rule 41 for IFC4 ParentBoundary validation on specific window/door boundaries was simplified because IDS cannot validate entity types within relationships.

### 07-units-geometry.ids
**Rules 51-54, 68**: Validates project units and geometric placement.

- Length, area, and volume units in project
- Object placement on all spatial elements and building elements

### 08-operational-parameters.ids
**Rules 55-64**: Validates operational parameters for energy simulation.

- Building air tightness
- Space ventilation (air flow, air change rate)
- Internal loads (lighting power density, equipment power density)
- Occupancy (density or number of occupants)
- HVAC zone existence (Rule 63 simplified - checks zones exist, not space-to-zone assignments)
- Temperature setpoints (heating and cooling)
- Ground contact indication for slabs

**Note**: Rule 63 was simplified because IDS `partOf` relationships can only be "required" or "prohibited", not "optional".

### 09-climate-solar.ids
**Rules 65-67**: Validates climate data and solar analysis requirements.

- Shading devices (IfcShadingDevice)
- Building true north orientation
- Design ambient temperature

## Usage

These IDS files can be used with IDS-compatible validation tools such as:

- [IfcTester](https://blenderbim.org/docs-python/ifctester/usage.html) (part of BlenderBIM)
- [IDS Validator](https://github.com/buildingSMART/IDS)

### Example with IfcTester

```bash
# Validate a single IDS file
python -m ifctester IDS/01-spatial-structure.ids model.ifc

# Validate all IDS files
for ids in IDS/*.ids; do
    python -m ifctester "$ids" model.ifc
done
```

## Rule Categories

The rules are organized by:

1. **CRITICAL** (Rules 1-30): Core requirements without which gbXML conversion will fail
   - Spatial structure, space properties, boundaries, materials

2. **ESSENTIAL** (Rules 31-54): Properties needed for meaningful energy analysis
   - Thermal properties, window/door properties, units

3. **RECOMMENDED** (Rules 55-68): Operational parameters that enhance analysis accuracy
   - Ventilation, internal loads, HVAC zones, climate data

## IDS Limitations

IDS (Information Delivery Specification) has specific capabilities and limitations. These rules were designed within IDS constraints:

### What IDS Can Validate
- **Entity existence**: Presence of specific IFC entities (e.g., IfcSite, IfcSpace)
- **Attribute values**: Required attributes and their values/constraints
- **Property sets**: Presence and values of properties in property sets
- **Material associations**: Entities having material assignments
- **Simple relationships**: Containment (partOf), type assignments (IsTypedBy)
- **Value ranges**: Numeric constraints on properties (min/max values)
- **Enumerations**: Attribute values from specific allowed sets

### What IDS Cannot Validate
Some energy model requirements are beyond IDS capabilities and require geometric/computational analysis tools:

- **Geometric calculations**: Boundary area sums, space enclosure completeness, boundary gaps, surface coverage
- **Mathematical relationships**: Reciprocal checks (e.g., U-value = 1/R-value)
- **Sequence/ordering**: Material layer ordering (exterior to interior)
- **Entity types in relationships**: Type of entity referenced by a relationship attribute
- **Multiple entity filters**: Checking relationships between specific entity type combinations
- **Optional relationships**: IDS relationships can only be "required" or "prohibited", not "optional"
- **Aggregated checks**: "No two entities should..." or "sum of..." validations
- **Conditional logic**: If entity A exists, then entity B must have property X

### Simplified Rules in These Files

Due to IDS limitations, some rules were simplified:

- **Rule 21**: Checks that boundary elements have `ProvidesBoundaries` attribute instead of validating specific element types in relationships
- **Rule 41**: Removed IFC4 ParentBoundary validation for specific window/door boundaries (IDS can't filter by entity type in relationships)
- **Rule 57**: Checks for `IsDefinedBy` attribute but cannot verify it references IfcDistributionSystem specifically
- **Rule 63**: Simplified to check that IfcZone entities exist, rather than validating space-to-zone assignments (partOf cannot be optional)

## Schema Support

All IDS files support both:
- **IFC2X3**: Older schema with different property set names
- **IFC4**: Current schema with standardized property sets

The specifications automatically adapt to the schema version used.

## Validation Strictness

Most rules use `cardinality="optional"` on property requirements because:
1. Not all properties are required in all scenarios
2. Different modeling workflows may use different property sets
3. Some properties are alternatives (e.g., R-value OR U-value)
4. Properties may exist at element level OR type level (IDS checks both via inheritance)

### IDS Cardinality Values

IDS uses different cardinality attributes for different facets:

- **Properties**: `cardinality="optional"` (default: "required") or `cardinality="prohibited"`
- **Attributes/Relationships**: No cardinality attribute - they are required by default unless the parent requirement has cardinality
- **Materials/Classifications**: `cardinality` as needed

For strict validation requiring specific properties, change `cardinality="optional"` to remove the attribute (making it required by default).

## Common IDS Patterns Used

These files demonstrate several IDS validation patterns:

### Pattern 1: Alternative Property Sets
```xml
<!-- Check for property in multiple possible property sets -->
<specification name="Space Has Area (IFC4 Qto)" ifcVersion="IFC4">
  <property cardinality="optional" dataType="IFCAREAMEASURE">
    <propertySet><simpleValue>Qto_SpaceBaseQuantities</simpleValue></propertySet>
    <baseName><simpleValue>NetFloorArea</simpleValue></baseName>
  </property>
</specification>
<specification name="Space Has Area (IFC2X3)" ifcVersion="IFC2X3">
  <property cardinality="optional" dataType="IFCAREAMEASURE">
    <propertySet><simpleValue>BaseQuantities</simpleValue></propertySet>
    <baseName><simpleValue>NetFloorArea</simpleValue></baseName>
  </property>
</specification>
```

### Pattern 2: Value Constraints
```xml
<!-- Validate numeric range -->
<property dataType="IFCTHERMALTRANSMITTANCEMEASURE" cardinality="optional">
  <propertySet><simpleValue>Pset_WallCommon</simpleValue></propertySet>
  <baseName><simpleValue>ThermalTransmittance</simpleValue></baseName>
  <value>
    <xs:restriction base="xs:double">
      <xs:minInclusive value="0.1"/>
      <xs:maxInclusive value="6.0"/>
    </xs:restriction>
  </value>
</property>
```

### Pattern 3: Enumeration Constraints
```xml
<!-- Attribute must be one of specific values -->
<attribute>
  <name><simpleValue>InternalOrExternalBoundary</simpleValue></name>
  <value>
    <xs:restriction base="xs:string">
      <xs:enumeration value="INTERNAL"/>
      <xs:enumeration value="EXTERNAL"/>
      <xs:enumeration value="EXTERNAL_EARTH"/>
      <xs:enumeration value="EXTERNAL_FIRE"/>
    </xs:restriction>
  </value>
</attribute>
```

### Pattern 4: Multiple Entity Types
```xml
<!-- Apply same requirement to multiple entity types -->
<entity>
  <name>
    <xs:restriction base="xs:string">
      <xs:enumeration value="IFCWALL"/>
      <xs:enumeration value="IFCSLAB"/>
      <xs:enumeration value="IFCROOF"/>
    </xs:restriction>
  </name>
</entity>
```

### Pattern 5: Relationship Validation
```xml
<!-- Check containment relationships -->
<partOf relation="IFCRELAGGREGATES">
  <entity>
    <name><simpleValue>IFCBUILDING</simpleValue></name>
  </entity>
</partOf>
```

### Testing

```bash
# Test all IDS files
for file in IDS/*.ids; do
    python -m ifctester "$file" model.ifc
done
```

The validation will show:
- **PASS**: Entity/property exists and meets requirements
- **FAIL**: Required entity/property missing or doesn't meet constraints
- Detailed error messages for each failure

Note: FAIL results indicate issues in your IFC model, not errors in the IDS files.

## Contributing

To add new rules:

1. **Choose the appropriate file** based on the validation category
2. **Use descriptive specification names** that clearly indicate what is being checked
3. **Follow IDS syntax conventions**:
   - Use `cardinality="optional"` for recommended properties
   - Use `instructions` attribute (not element) for guidance text
   - Properties use `dataType` attribute (e.g., `dataType="IFCLENGTHMEASURE"`)
   - Attributes reference IFC attribute names exactly (case-sensitive)
4. **Test thoroughly**:
   - Validate IDS syntax: `python -m ifctester your-file.ids model.ifc`
   - Test with both IFC2X3 and IFC4 models if applicable
   - Verify error messages are clear and actionable
5. **Document limitations**: Note any IDS limitations in comments within the file
6. **Update this README** with the new rule number and description

## Troubleshooting

### Common IDS Errors

**Error: "minOccurs attribute not allowed"**
- **Cause**: Using `minOccurs` on elements that don't support it
- **Fix**: Use `cardinality="optional"` for properties, or remove the attribute entirely for required elements

**Error: "Unexpected child with tag 'ids:instructions'"**
- **Cause**: Using `<instructions>` as a child element
- **Fix**: Use `instructions="text"` as an attribute instead

**Error: "Unexpected child with tag 'ids:entity' at position 2"**
- **Cause**: Multiple `<entity>` elements in `<applicability>`
- **Fix**: IDS only allows one entity per applicability; create separate specifications or use entity enumeration

**Error: "value must be one of ['required', 'prohibited']"**
- **Cause**: Using `cardinality="optional"` on facets that don't support it (e.g., `partOf`)
- **Fix**: For relationships, use `cardinality="required"` or `cardinality="prohibited"`, or omit for default behavior

### Validation Tips

1. **Property inheritance**: IDS automatically checks properties on both element instances and their types (via `IsTypedBy`)
2. **Case sensitivity**: IFC entity names and attribute names are case-sensitive (use UPPERCASE for entities)
3. **Data types**: Property `dataType` must match IFC schema (e.g., `IFCLENGTHMEASURE`, not `IfcLengthMeasure`)
4. **Empty requirements**: `<requirements/>` is valid and checks only that the entity exists
5. **Schema versions**: Use `ifcVersion="IFC2X3 IFC4"` to support both schemas in one specification

## References

### IDS Documentation
- [IDS Specification](https://technical.buildingsmart.org/projects/information-delivery-specification-ids/)
- [IDS GitHub Repository](https://github.com/buildingSMART/IDS)
- [IDS Examples](https://github.com/buildingSMART/IDS/tree/master/Documentation/examples)

### IFC Documentation
- [IFC Schema Documentation](https://standards.buildingsmart.org/IFC)
- [IFC4 Documentation](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/)
- [IFC2X3 Documentation](https://standards.buildingsmart.org/IFC/RELEASE/IFC2x3/TC1/HTML/)

### Tools
- [IfcTester Documentation](https://blenderbim.org/docs-python/ifctester/usage.html)
- [IfcOpenShell](http://ifcopenshell.org/)
- [gbXML Schema](https://www.gbxml.org/)
