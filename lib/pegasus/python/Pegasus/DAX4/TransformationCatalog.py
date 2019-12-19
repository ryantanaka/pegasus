import json
from enum import Enum
from collections import defaultdict

import yaml

from .Mixins import ProfileMixin
from .SiteCatalog import Architecture
from .Encoding import filter_out_nones, FileFormat, CustomEncoder
from .Errors import DuplicateError, NotFoundError

PEGASUS_VERSION = "5.0"


class TransformationType(Enum):
    """Specifies the type of the transformation. STAGEABLE denotes that it can
    be shipped around as a file. INSTALLED denotes that the transformation is
    installed on a specified machine, and that it cannot be shipped around as
    a file to be executed somewher else. 
    """

    STAGEABLE = "stageable"
    INSTALLED = "installed"


class TransformationSite(ProfileMixin):
    """Site specific information about a Transformation. Transformations will contain
    at least one TransformationSite object which includes, at minimum, the name of the site,
    the transformation's pfn on that site and whether or not it is installed or stageable at
    that site.  
    """

    def __init__(
        self,
        name,
        pfn,
        transformation_type,
        arch=None,
        os_type=None,
        os_release=None,
        os_version=None,
        glibc=None,
        container=None,
    ):
        """Constructor
        
        :param name: site name associated with this transformation
        :type name: str
        :param pfn: physical file name
        :type pfn: str
        :param type: TransformationType.STAGEABLE or TransformationType.INSTALLED
        :type type: TransformationType
        :param arch: Architecture that this transformation was compiled for, defaults to None
        :type arch: Architecture, optional
        :param os_type: Name of os that this transformation was compiled for, defaults to None
        :type os_type: str, optional
        :param os_release: Release of os that this transformation was compiled for, defaults to None, defaults to None
        :type os_release: str, optional
        :param os_version: Version of os that this transformation was compiled for, defaults to None, defaults to None
        :type os_version: str, optional
        :param glibc: Version of glibc this transformation was compiled against, defaults to None
        :type glibc: str, optional
        :param container: specify the container to use, optional
        :type container: str 
        """

        self.name = name
        self.pfn = pfn

        if not isinstance(transformation_type, TransformationType):
            raise ValueError("type must be one of TransformationType")

        self.transformation_type = transformation_type.value

        if arch is not None:
            if not isinstance(arch, Architecture):
                raise ValueError("arch must be one of Arch")
            else:
                self.arch = arch.value

        self.os_type = os_type
        self.os_release = os_release
        self.os_version = os_version
        self.glibc = glibc
        self.container = container

        self.profiles = defaultdict(dict)

    def __json__(self):

        return filter_out_nones(
            {
                "name": self.name,
                "pfn": self.pfn,
                "type": self.transformation_type,
                "arch": self.arch,
                "os.type": self.os_type,
                "os.release": self.os_release,
                "os.version": self.os_version,
                "glibc": self.glibc,
                "container": self.container,
                "profiles": dict(self.profiles) if len(self.profiles) > 0 else None,
            }
        )


class ContainerType(Enum):
    """Container types recognized by Pegasus"""

    DOCKER = "docker"
    SINGULARITY = "singularity"
    SHIFTER = "shifter"


class Container(ProfileMixin):
    def __init__(self, name, container_type, image, mount, image_site=None):
        """Constructor
        
        :param name: name of this container
        :type name: str
        :param container_type: a type defined in ContainerType
        :type container_type: ContainerType
        :param image: image, such as 'docker:///rynge/montage:latest'
        :type image: str
        :param mount: mount, such as '/Volumes/Work/lfs1:/shared-data/:ro'
        :type mount: str
        :param image_site: optional site attribute to tell pegasus which site tar file exists, defaults to None
        :type image_site: str, optional
        :raises ValueError: container_type must be one of ContainerType
        """
        self.name = name

        if not isinstance(container_type, ContainerType):
            raise ValueError("container_type must be one of ContainerType")

        self.container_type = container_type.value
        self.image = image
        self.mount = mount
        self.image_site = image_site

        self.profiles = defaultdict(dict)

    def __json__(self):
        return filter_out_nones(
            {
                "name": self.name,
                "type": self.container_type,
                "image": self.image,
                "mount": self.mount,
                "imageSite": self.image_site,
                "profiles": dict(self.profiles) if len(self.profiles) > 0 else None,
            }
        )


# TODO: refactor so that:
# 1. Transformation is a hash of name, namespace, and version
# 2. requires takes in a transformation and not transformation name
# 3. TransformationCatalog.add_transformation(...) takes in as input a Transformation object
# 4. TransformationCatalog.has_transformation(...) takes in as input a Transformation object
# 5. get Transformation doesn't really make sense as we already have it... (because it was created)

# class Transformation(ProfileMixin, HookMixin)
class Transformation(ProfileMixin):
    """A transformation, which can be a standalone executable, or one that
        requires other executables. Transformations can reside on one or
        more sites where they are either stageable (a binary that can be shipped
        around) or installed.
    """

    def __init__(
        self, name, namespace=None, version=None,
    ):
        """Constructor

        :param name: Logical name of executable
        :type name: str
        :param namespace: Transformation namespace
        :type namespace: str, optional
        :param version: Transformation version, defaults to None
        :type version: str, optional
        """
        self.name = name
        self.namespace = namespace
        self.version = version
        self.key = (self.name, self.namespace, self.version)

        self.sites = dict()
        self.requires = set()

        self.profiles = defaultdict(dict)
        self.hooks = dict()

    def add_site(
        self,
        name,
        pfn,
        transformation_type,
        arch=None,
        ostype=None,
        osrelease=None,
        osversion=None,
        glibc=None,
        container=None,
    ):
        """Add a TransformationSite to this Transformation
        
        :param name: site name associated with this transformation
        :type name: str
        :param pfn: physical file name
        :type pfn: str
        :param type: TransformationType.STAGEABLE or TransformationType.INSTALLED
        :type type: TransformationType
        :param arch: Architecture that this transformation was compiled for, defaults to None
        :type arch: Architecture, optional
        :param os: Name of os that this transformation was compiled for, defaults to None
        :type os: str, optional
        :param osrelease: Release of os that this transformation was compiled for, defaults to None, defaults to None
        :type osrelease: str, optional
        :param osversion: Version of os that this transformation was compiled for, defaults to None, defaults to None
        :type osversion: str, optional
        :param glibc: Version of glibc this transformation was compiled against, defaults to None
        :type glibc: str, optional
        :param container: specify the container to use, optional
        :type container: str 
        :raises DuplicateError: a site with this is already associated to this Transformation
        """

        if name in self.sites:
            raise DuplicateError(
                "Site {0} already exists for transformation {1}".format(name, self.name)
            )

        if not isinstance(transformation_type, TransformationType):
            raise ValueError("type must be one of TransformationType")

        if arch is not None:
            if not isinstance(arch, Architecture):
                raise ValueError("arch must be one of Arch")

        self.sites[name] = TransformationSite(
            name,
            pfn,
            transformation_type,
            arch,
            ostype,
            osrelease,
            osversion,
            glibc,
            container,
        )

        return self

    def get_site(self, name):
        """Retrieve a TransformationSite object associated with this 
        Transformation by site name

        
        :param name: site name
        :type name: str
        :raises NotFoundError: the site has not been added for this Transformation
        :return: the TransformationSite object associated with this Transformation 
        :rtype: TransformationSite
        """
        if name not in self.sites:
            raise NotFoundError(
                "Site {0} not found for transformation {1}".format(name, self.name)
            )

        return self.sites[name]

    def has_site(self, name):
        """Check if a site has been added for this Transformation
        
        :param name: site name
        :type name: str
        :return: True if site has been added, else False
        :rtype: bool
        """
        return name in self.sites

    def remove_site(self, name):
        """Remove the given site from this Transformation
        
        :param name: name of site to be removed
        :type name: str
        :raises NotFoundError: the site has not been added for this Transformation 
        """
        if name not in self.sites:
            raise NotFoundError(
                "Site {0} not found for transformation {1}".format(name, self.name)
            )

        del self.sites[name]

        return self

    def add_site_profile(self, site_name, namespace, key, value):
        if site_name not in self.sites:
            raise NotFoundError(
                "Site {0} not found for transformation {1}".format(site_name, self.name)
            )

        self.sites[site_name].add_profile(namespace, key, value)

        return self

    def add_requirement(self, required_transformation):
        """Add a requirement to this Transformation
        
        :param required_transformation: Transformation that this transformation requires
        :type required_transformation: Transformation
        :raises DuplicateError: this requirement already exists
        :return: self
        :rtype: Transformation
        """
        if required_transformation in self.requires:
            raise DuplicateError(
                "Transformation {0} already requires {1}".format(
                    self.name, required_transformation.name
                )
            )

        self.requires.add(required_transformation)

        return self

    def has_requirement(self, transformation):
        """Check if this Transformation requires the given transformation
        
        :param transformation: the Transformation to check for 
        :type transformation: Transformation
        :return: whether or not this Transformation requires the given Transformation
        :rtype: bool
        """
        return transformation in self.requires

    def remove_requirement(self, transformation):
        """Remove a requirement from this Transformation
        
        :param transformation: the Transformation to be removed from the list of requirements
        :type transformation: Transformation
        :raises NotFoundError: this requirement does not exist
        """
        if not self.has_requirement(transformation):
            raise NotFoundError(
                "Transformation {0} does not have requirement {1}".format(
                    self.name, str(transformation)
                )
            )

        self.requires.remove(transformation)

        return self

    def __json__(self):
        return filter_out_nones(
            {
                "namespace": self.namespace,
                "name": self.name,
                "version": self.version,
                "requires": [req.name for req in self.requires]
                if len(self.requires) > 0
                else None,
                "sites": [site.__json__() for name, site in self.sites.items()],
                "profiles": dict(self.profiles) if len(self.profiles) > 0 else None,
                "hooks": self.hooks if len(self.hooks) > 0 else None,
            }
        )

    def __str__(self):
        return "<Transformation {0}::{1}:{2}>".format(
            self.namespace, self.name, self.version
        )

    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        if isinstance(other, Transformation):
            return self.key == other.key
        return ValueError("must compare with type Transformation")


class TransformationCatalog:
    """TransformationCatalog class maintains a list a Transformations, site specific
    Transformation information, and a list of containers
    """

    def __init__(self, default_filepath="TransformationCatalog"):
        """Constructor
        
        :param filepath: filepath to write this catalog to , defaults to "TransformationCatalog.yml"
        :type filepath: str, optional
        """
        self.default_filepath = default_filepath
        self.transformations = dict()
        self.containers = dict()

    def add_transformations(self, *transformations):
        for tr in transformations:
            if not isinstance(tr, Transformation):
                raise ValueError("input must be of type Transformation")

            if self.has_transformation(tr):
                raise DuplicateError("transformation already exists in catalog")

            self.transformations[tr.key] = tr

    def has_transformation(self, transformation):
        return transformation.key in self.transformations

    def add_container(self, name, container_type, image, mount, image_site=None):
        """Retrieve a container by its name
        
        :param name: name of this container
        :type name: str
        :param container_type: a type defined in ContainerType
        :type container_type: ContainerType
        :param image: image, such as 'docker:///rynge/montage:latest'
        :type image: str
        :param mount: mount, such as '/Volumes/Work/lfs1:/shared-data/:ro'
        :type mount: str
        :param image_site: optional site attribute to tell pegasus which site tar file exists, defaults to None
        :type image_site: str, optional
        :raises DuplicateError: a Container with this name already exists
        :raises ValueError: container_type must be one of ContainerType
        :return: self
        :rtype: TransformationCatalog
        """
        if self.has_container(name):
            raise DuplicateError("Container {0} already exists".format(name))

        if not isinstance(container_type, ContainerType):
            raise ValueError("container_type must be one of ContainerType")

        self.containers[name] = Container(
            name, container_type, image, mount, image_site
        )

        return self

    def has_container(self, name):
        """Check if a container exists in this catalog
        
        :param name: name of the container
        :type name: str
        :return: wether or not the container exists in this catalog
        :rtype: bool
        """
        return name in self.containers

    def get_container(self, name):
        """Retrieve a container from this catalog by its name
        
        :param name: Container name
        :type name: str
        :raises NotFoundError: a Container by this name does not exist in this catalog
        :return: the Container with the given name
        :rtype: Container
        """
        if not self.has_container(name):
            raise NotFoundError(
                "Container {0} does not exist in this catalog".format(name)
            )

        return self.containers[name]

    def remove_container(self, name):
        """Remove a conatiner with the given name
        
        :param name: container name
        :type name: str
        :raises NotFoundError: the Container with the given name does not exist in this catalog
        :return: self
        :rtype: TransformationCatalog
        """
        if not self.has_container(name):
            raise NotFoundError(
                "Container {0} does not exist in this catalog".format(name)
            )

        del self.containers[name]

        return self

    def write(self, non_default_filepath="", file_format=FileFormat.YAML):
        """Write this catalog, formatted in YAML, to a file
        
        :param filepath: path to which this catalog will be written, defaults to self.filepath if filepath is "" or None
        :type filepath: str, optional
        """
        if not isinstance(file_format, FileFormat):
            raise ValueError("invalid file format {}".format(file_format))

        path = self.default_filepath
        if non_default_filepath != "":
            path = non_default_filepath
        else:
            if file_format == FileFormat.YAML:
                path = ".".join([self.default_filepath, FileFormat.YAML.value])
            elif file_format == FileFormat.JSON:
                path = ".".join([self.default_filepath, FileFormat.JSON.value])

        with open(path, "w") as file:
            if file_format == FileFormat.YAML:
                yaml.dump(CustomEncoder().default(self), file)
            elif file_format == FileFormat.JSON:
                json.dump(self, file, cls=CustomEncoder, indent=4)

    def __json__(self):
        return filter_out_nones(
            {
                "pegasus": PEGASUS_VERSION,
                "transformations": [
                    t.__json__() for key, t in self.transformations.items()
                ],
                "containers": [c.__json__() for key, c in self.containers]
                if len(self.containers) > 0
                else None,
            }
        )
