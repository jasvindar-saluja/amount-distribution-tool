from flask import Flask, request, jsonify, render_template, make_response, send_from_directory
import csv
import io

from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageTemplate, Frame
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.pdfgen import canvas

app = Flask(__name__)

# Register the Noto Sans font to support the ₹ symbol
pdfmetrics.registerFont(TTFont('NotoSans', 'fonts/NotoSans-Regular.ttf'))

# Serve index.html from the root directory
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

# Serve static files from the assets folder for assets like logo and favicon
@app.route('/assets/<path:filename>')
def static_assets(filename):
    return send_from_directory('assets', filename)

# Route to serve favicon.ico
@app.route('/favicon.ico')
def favicon():
    return send_from_directory('assets', 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.json
    total_amount = data["total_amount"]
    contributors = data["contributors"]
    receivers = data["receivers"]

    # Initialize matrix structure
    matrix = []
    overall_total = 0

    # Step through receiver groups and calculate for each receiver member
    for receiver_group in receivers:
        receiver_group_total = 0
        group_matrix = {"group_name": receiver_group["name"], "members": []}

        for receiver_member in receiver_group["members"]:
            member_total = 0
            member_row = {"receiver": receiver_member, "details": []}

            # Calculate amounts contributed by each contributor group and member
            for contributor_group in contributors:
                group_contribution = (contributor_group["percentage"] / 100) * total_amount
                for contributor_member in contributor_group["members"]:
                    member_share = group_contribution / len(contributor_group["members"])
                    receiver_share = (receiver_group["percentage"] / 100) * (1 / len(receiver_group["members"]))
                    amount_contributed = member_share * receiver_share

                    member_total += amount_contributed
                    member_row["details"].append({"contributor": contributor_member.strip(), "amount": amount_contributed})

            receiver_group_total += member_total
            member_row["subtotal"] = member_total
            group_matrix["members"].append(member_row)

        group_matrix["group_total"] = receiver_group_total
        overall_total += receiver_group_total
        matrix.append(group_matrix)

    return jsonify({"matrix": matrix, "overall_total": overall_total})

@app.route("/export_csv", methods=["POST"])
def export_csv():
    data = request.json["matrix"]
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write CSV title and headers
    writer.writerow(["Amount Distribution Report"])
    writer.writerow(["Receiver Group", "Receiver Member", "Contributor", "Amount (₹)"])

    # Write receiver data
    for group in data:
        for member in group["members"]:
            for detail in member["details"]:
                writer.writerow([group["group_name"].strip(), member["receiver"].strip(), detail["contributor"].strip(), detail["amount"]])

    # Insert a blank row to separate perspectives
    writer.writerow([])

    # Add contributor's perspective
    contributor_data = {}
    for group in data:
        for member in group["members"]:
            for detail in member["details"]:
                if detail["contributor"] not in contributor_data:
                    contributor_data[detail["contributor"]] = []
                contributor_data[detail["contributor"]].append({
                    "receiver_group": group["group_name"],
                    "receiver_member": member["receiver"],
                    "amount": detail["amount"]
                })

    writer.writerow(["Contributor View"])
    writer.writerow(["Contributor", "Receiver Group / Member", "Amount (₹)"])

    for contributor, contributions in contributor_data.items():
        for entry in contributions:
            writer.writerow([contributor, f"{entry['receiver_group']} - {entry['receiver_member']}", entry["amount"]])

    output.seek(0)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=amount_distribution.csv"
    response.headers["Content-Type"] = "text/csv"
    return response

# Function to draw the header and footer
def add_page_header_footer(canvas, doc):
    canvas.saveState()
    
    # Draw header
    canvas.setFont("NotoSans", 12)

    # Center-align title
    canvas.drawCentredString(400, 550, "Amount Distribution Report")

    # Add logo
    logo_path = "assets/logo.png"
    try:
        canvas.drawImage(logo_path, 30, 550, width=50, height=50, preserveAspectRatio=True, mask='auto')
    except Exception as e:
        print(f"Server error: {e}")
        return jsonify({"error": str(e)}), 500

    # Draw footer
    canvas.setFont("NotoSans", 10)
    canvas.drawCentredString(400, 30, "© 2025 Your Company Name. All rights reserved.")

    canvas.restoreState()

@app.route("/export_pdf", methods=["POST"])
def export_pdf():
    data = request.json["matrix"]
    output = io.BytesIO()
    pdf = SimpleDocTemplate(output, pagesize=landscape(letter))

    elements = [Paragraph("Amount Distribution Report", getSampleStyleSheet()['Title'])]

    # Set up table styles
    style = getSampleStyleSheet()
    style['Normal'].fontName = 'NotoSans'

    elements = [Paragraph("Amount Distribution Report", style['Title'])]

    # Receiver's Perspective Table
    elements.append(Paragraph("Receiver's Perspective", style['Heading2']))
    table_data = [["Receiver Group", "Receiver Member", "Contributor", "Amount (₹)"]]

    for group in data:
        for member in group["members"]:
            for detail in member["details"]:
                table_data.append([
                    group["group_name"],
                    member["receiver"],
                    detail["contributor"],
                    f"₹{detail['amount']:.2f}"
                ])

    # Create and style the table
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'NotoSans'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(table)

    # Build the PDF with the header and footer on each page
    pdf.build(elements, onFirstPage=add_page_header_footer, onLaterPages=add_page_header_footer)

    # Contributor's Perspective Table
    elements.append(Paragraph("Contributor's Perspective", style['Heading2']))
    contributor_data = {}
    for group in data:
        for member in group["members"]:
            for detail in member["details"]:
                if detail["contributor"] not in contributor_data:
                    contributor_data[detail["contributor"]] = []
                contributor_data[detail["contributor"]].append({
                    "receiver_group": group["group_name"],
                    "receiver_member": member["receiver"],
                    "amount": detail["amount"]
                })

    table_data = [["Contributor", "Receiver Group / Member", "Amount (₹)"]]

    for contributor, contributions in contributor_data.items():
        for entry in contributions:
            table_data.append([contributor, f"{entry['receiver_group']} - {entry['receiver_member']}", f"₹{entry['amount']:.2f}"])

    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'NotoSans'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)

    pdf.build(elements)
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=amount_distribution.pdf"
    response.headers["Content-Type"] = "application/pdf"
    return response

@app.errorhandler(404)
def page_not_found(e):
    return "Page not found!", 404

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
