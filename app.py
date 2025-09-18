import streamlit as st
import trimesh
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# =====================
# Materials & densities
# =====================
MATERIALS = {
    "PLA": 1.250, "PETG": 1.270, "ABS": 1.020, "Resin": 1.200, "TPU (Rubber-like)": 1.200,
    "Polyamide_SLS": 0.950, "Polyamide_MJF": 1.010, "Plexiglass": 1.180, "Alumide": 1.360,
    "Carbon Steel": 7.800, "Steel": 7.860, "Aluminum": 2.698, "Titanium": 4.410,
    "Brass": 8.600, "Bronze": 9.000, "Copper": 9.000, "Silver": 10.260,
    "Gold_14K": 13.600, "Gold_18K": 15.600, "3k CFRP": 1.790, "Red Oak": 5.700
}

# =====================
# Compute model details
# =====================
def calculate_model_data(file, ext, infill=1.0):
    mesh = trimesh.load(file, file_type=ext, force="mesh")
    file_size = file.size / 1024  # KB
    triangles = len(mesh.faces)
    bounds = mesh.bounding_box.extents / 10.0  # mm → cm
    surface_area = mesh.area / 100.0  # mm² → cm²
    volume = mesh.volume / 1000.0  # mm³ → cm³

    model_info = {
        "File Size": f"{file_size:.2f} KB",
        "Triangles": triangles,
        "Bounding Box (cm)": f"W: {bounds[0]:.2f}, D: {bounds[1]:.2f}, H: {bounds[2]:.2f}",
        "Surface Area": f"{surface_area:.4f} cm²",
        "Volume (solid)": f"{volume:.4f} cm³",
    }

    rows = []
    for i, (mat, density) in enumerate(MATERIALS.items(), start=1):
        mass_100 = volume * density
        mass_infill = mass_100 * infill
        rows.append([i, mat, density, mass_infill, mass_100])

    df = pd.DataFrame(
        rows,
        columns=["ID", "Material", "Density", f"Mass @{infill*100:.1f}% (g)", "Mass @100% (g)"]
    )
    return mesh, model_info, df

# =====================
# 3D Visualization with manual measuring arrows
# =====================
def plot_stl_with_arrows(mesh, material_name, mass_value, color_by="z", measure_lines=[]):
    vertices = mesh.vertices
    faces = mesh.faces
    x, y, z = vertices[:, 0], vertices[:, 1], vertices[:, 2]
    i, j, k = faces[:, 0], faces[:, 1], faces[:, 2]

    if color_by == "z":
        colors = z
    elif color_by == "curvature":
        colors = mesh.vertex_defects
    else:
        center = mesh.centroid
        colors = ((x - center[0])**2 + (y - center[1])**2 + (z - center[2])**2) ** 0.5

    fig = go.Figure(data=[go.Mesh3d(
        x=x, y=y, z=z,
        i=i, j=j, k=k,
        intensity=colors,
        colorscale="Jet",
        opacity=1.0,
        flatshading=True
    )])

    # Add manual measurement lines
    for line in measure_lines:
        p1, p2 = line
        fig.add_trace(go.Scatter3d(
            x=[p1[0], p2[0]],
            y=[p1[1], p2[1]],
            z=[p1[2], p2[2]],
            mode='lines+markers+text',
            marker=dict(size=4, color='red'),
            line=dict(color='red', width=4),
            text=[f"{np.linalg.norm(p1-p2)/10:.2f} cm", ""],
            textposition="top center",
            name=f"Distance: {np.linalg.norm(p1-p2)/10:.2f} cm"
        ))

    fig.add_annotation(
        text=f"<b>Material:</b> {material_name}<br><b>Mass:</b> {mass_value:.2f} g",
        xref="paper", yref="paper",
        x=0.02, y=0.98,
        showarrow=False,
        font=dict(size=14, color="white"),
        bgcolor="black",
        bordercolor="white",
        borderpad=6
    )

    fig.update_layout(
        scene=dict(xaxis_title="X", yaxis_title="Y", zaxis_title="Z"),
        margin=dict(l=0, r=0, t=0, b=0),
        height=600
    )
    return fig

# =====================
# Streamlit App
# =====================
st.set_page_config(page_title="3D Model Mass & Measurement Tool", layout="wide")
st.title("📦 3D Model Mass, Volume & Manual Measurement Tool")

col1, col2 = st.columns([1, 2])

# LEFT COLUMN: Upload & analysis
with col1:
    file_type_choice = st.selectbox("Select File Type", ["STL", "STEP", "Parasolid", "NX Part"])
    file_extensions = {"STL":["stl"], "STEP":["step","stp"], "Parasolid":["x_t","x_b"], "NX Part":["prt"]}
    uploaded_files = st.file_uploader(f"Upload your {file_type_choice} files", type=file_extensions[file_type_choice], accept_multiple_files=True)

    infill_percent = st.slider("Select infill percentage (%)", 0, 100, 100, 5)
    infill = infill_percent / 100.0

    all_meshes = {}
    all_model_info = {}
    all_mass_dfs = {}
    measure_lines_dict = {}

    if uploaded_files:
        for uploaded_file in uploaded_files:
            ext = uploaded_file.name.split(".")[-1].lower()
            if ext == "stp": ext="step"
            st.success(f"✅ Uploaded File: **{uploaded_file.name}** ({uploaded_file.type or 'unknown'}) — {uploaded_file.size/1024:.2f} KB")

            mesh, model_info, mass_df = calculate_model_data(uploaded_file, ext, infill)
            all_meshes[uploaded_file.name] = mesh
            all_model_info[uploaded_file.name] = model_info
            all_mass_dfs[uploaded_file.name] = mass_df

            # Manual measurement input
            st.subheader(f"📐 Manual Measurement: {uploaded_file.name}")
            vertex_count = len(mesh.vertices)
            point1_idx = st.number_input(f"Vertex 1 index ({uploaded_file.name})", 0, vertex_count-1, 0, key=f"{uploaded_file.name}_v1")
            point2_idx = st.number_input(f"Vertex 2 index ({uploaded_file.name})", 0, vertex_count-1, 1, key=f"{uploaded_file.name}_v2")
            measure_lines_dict[uploaded_file.name] = [[mesh.vertices[point1_idx], mesh.vertices[point2_idx]]]

# RIGHT COLUMN: Side-by-side 3D Visualization with per-file material selection + model info below each
with col2:
    if uploaded_files:
        st.subheader("🎨 3D Visualization Side-by-Side with Model Analysis")
        n_files = len(all_meshes)
        cols_per_row = 2
        rows = (n_files + cols_per_row - 1) // cols_per_row
        mesh_items = list(all_meshes.items())

        for r in range(rows):
            row_cols = st.columns(cols_per_row)
            for c in range(cols_per_row):
                idx = r * cols_per_row + c
                if idx >= n_files:
                    break
                file_name, mesh = mesh_items[idx]
                with row_cols[c]:
                    st.write(f"**{file_name}**")
                    # Per-file material selection
                    selected_material = st.selectbox(f"Select Material ({file_name})", MATERIALS.keys(), key=f"mat_{file_name}")
                    stress_option = st.radio(f"Color by ({file_name}):", ["z","curvature","distance"], key=f"stress_{file_name}")
                    mass_value = all_mass_dfs[file_name].loc[
                        all_mass_dfs[file_name]["Material"] == selected_material,
                        "Mass @100% (g)"
                    ].values[0]
                    # Show 3D visualization
                    st.plotly_chart(
                        plot_stl_with_arrows(
                            mesh, selected_material, mass_value,
                            stress_option, measure_lines_dict[file_name]
                        ),
                        use_container_width=True
                    )
                    # Show model analysis below the visualization
                    st.subheader(f"📑 Model Analysis: {file_name}")
                    st.table(pd.DataFrame(all_model_info[file_name].items(), columns=["Property", "Value"]))
                    st.subheader(f"⚖️ Mass Estimates: {file_name}")
                    st.dataframe(all_mass_dfs[file_name], use_container_width=True)
