import xml.etree.ElementTree as ET
import sys
import re

def parse_palo_alto_config(file_path, root):
    tree = ET.parse(file_path)

    # Fetch all <entry> elements and filter for 'ae' interfaces with VLANs in Python
    all_entries = root.findall(".//entry")
    vlan_interfaces = [entry for entry in all_entries if entry.get('name', '').startswith('ae') or entry.get('name', '').startswith('eth') and '.' in entry.get('name', '')]
    #eth_vlan_interfaces = [entry for entry in all_entries if entry.get('name', '').startswith('eth') and '.' in entry.get('name', '')]

    return vlan_interfaces

def extract_dhcp_relay_info(interface, root):
    # Extract DHCP relay information
    dhcp_relay_servers = []
    for dhcp_entry in root.findall(f".//dhcp/interface/entry[@name='{interface.get('name')}']/relay/ip/server/member"):
        dhcp_relay_servers.append(dhcp_entry.text)
    if dhcp_relay_servers is not None:
        return dhcp_relay_servers  # or any other relevant data extraction
    return None

def parse_palo_alto_config_routing(root):
    fortigate_config_routing = ""

    # BGP Configuration
    bgp_config = root.find(".//bgp")
    if bgp_config is not None:
        fortigate_config_routing += convert_bgp_config(bgp_config)

    # OSPF Configuration
    ospf_config = root.find(".//ospf")
    if ospf_config is not None:
        fortigate_config_routing += convert_ospf_config(ospf_config)

    # Static Routes
    static_routes = root.findall(".//static-route/entry")
    if static_routes:
        fortigate_config_routing += convert_static_routes(static_routes)

    return fortigate_config_routing

def convert_bgp_config(bgp_xml):
    config = "config router bgp\n"
    router_id = bgp_xml.find('router-id').text  
    config += f"    set router-id {router_id}\n"
    config += f"    set as {bgp_xml.find('local-as').text}\n"
    config += f"    config neighbor-group\n"

    #findrouterid
    # Assuming you have the local AS number somewhere in your XML or as a variable

    # Iterate through peer groups and peers
    for peer_group in bgp_xml.findall('.//peer-group/entry'):
        group_name = peer_group.get('name')
        remote_as = peer_group.find('.//peer-as').text
        interface = re.sub('^eth.*\.|^ae[0-9]+\.', 'VLan-', peer_group.find('./peer/entry/local-address/interface').text)        
        config += f"      edit \"{group_name}\"\n"
        config += f"        set interface {interface}\n"
        config += f"        set remote-as {remote_as}\n"
        config += f"        set soft-reconfiguration enable\n"
        config += f"      next\n"
    config += f"    end\n"
    config += f"    config neighbor\n"
    for peer_group in bgp_xml.findall('.//peer-group/entry'):    
        for peer in peer_group.findall('.//peer/entry'):
            peer_ip = peer.find('.//peer-address/ip').text
            
            config += f"      edit \"{peer_ip}\"\n"
            config += f"        set description {peer.get('name')}\n"
            config += f"        set neighbor-group \"{group_name}\"\n"
            # Add more BGP neighbor settings here as needed
            config += f"      next\n"
    config += f"    end\n"

    # Add more global BGP settings here as needed

    config += "end\n"
    return config

def convert_ospf_config(ospf_config):
    # Add OSPF specific conversion logic here
    # This is a placeholder function
    return '\n'#"OSPF configuration placeholder\n"

def convert_static_routes(static_routes):
    config = ""
    config += f"config router static\n"
    for route in static_routes:
        destination = route.find('destination').text if route.find('destination') is not None else "Unknown"
        nexthop_element = route.find('.//nexthop/ip-address')
        nexthop = nexthop_element.text if nexthop_element is not None else None
        if nexthop_element is None:
            continue
        device = re.sub('^eth.*\.|^ae[0-9]+\.', 'VLan-', route.find('.//interface').text)
        config += f"    edit 0\n"
        config += f"        set dst {destination}\n"
        config += f"        set gateway {nexthop}\n"
        config += f"        set device {device}\n"
        config += f"    next\n"
    config += f"end\n"
    return config

def convert_interfaces_to_fortigate(vlan_interfaces, root):
    fortigate_config = ""
    fortigate_config += f"config system interface\n"
    for interface in vlan_interfaces:      
        ip_entry = interface.find('.//ip/entry')
        if ip_entry is None:
            continue
        name = re.sub('^eth.*\.|^ae[0-9]+\.', 'VLan-', interface.get('name'))
        comment = interface.find('.//comment').text if interface.find('.//comment') is not None else 'No description'
        ip = ip_entry.get('name')
        vlan_id = interface.find('.//tag').text if interface.find('.//tag') is not None else 'no vlan'
        dhcp_relay_servers = extract_dhcp_relay_info(interface, root)

        # Format for FortiGate
        fortigate_config += f"edit {name}\n"
        fortigate_config += f"    set vdom root\n"
        fortigate_config += f"    set ip {ip}\n"
        fortigate_config += f"    set interface \"Inside-LAGG\"\n"
        fortigate_config += f"    set vlanid {vlan_id}\n"
        fortigate_config += f"    set alias \"{comment}\"\n"
        fortigate_config += "    set allowaccess ping\n"  # Example setting, adjust as needed
        if len(dhcp_relay_servers) == 0:
            fortigate_config += "next\n"
        else:
            fortigate_config += "    set dhcp-relay-service enable\n"
            fortigate_config += f"   set dhcp-relay-ip {' ' .join(dhcp_relay_servers)}\n"
            fortigate_config += "next\n"
    fortigate_config += f"end\n"
    return fortigate_config

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_palo_alto_config.xml>")
        sys.exit(1)

    palo_config_file = sys.argv[1]
    root = ET.parse(palo_config_file).getroot()
    vlan_interfaces = parse_palo_alto_config(palo_config_file, root)
    fortigate_config_interfaces = convert_interfaces_to_fortigate(vlan_interfaces, root)
    fortigate_config_routing = parse_palo_alto_config_routing(root)
    hostname = str(root.find('.//hostname').text)

    with open(hostname + '.txt' , 'w') as file:
        file.write(fortigate_config_interfaces)
        file.write(fortigate_config_routing)


    print(f"FortiGate configuration has been written to {hostname}.txt")

if __name__ == "__main__":
    main()